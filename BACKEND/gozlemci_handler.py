import threading
import time

from libs.lidar_controller import Lidar_Handler
from libs.joystick_handler import Joystick_Handler
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler
from libs.utils import calc_angle_distance, joystick_value_split

from pymavlink_custom.pymavlink_custom import Vehicle, calc_pos, calc_distance

#TODO: bu kod ikili icin dizayn edilcek
#TODO: sadece _hedef_koordinat_hesapla kodu coklu hedef icin duzenlencek

class Gozlemci:
    def __init__(self, vehicle: Vehicle, drone_conf: dict, stop_event: threading.Event=threading.Event()):
        self.drone_conf = drone_conf

        self.drone_id = self.drone_conf["id"]
        self.alt = self.drone_conf["alt"]
        self.rasp_ip = self.drone_conf["rasp-ip"]
        self.udp_port = self.drone_conf["udp-port"]
        self.tcp_port = self.drone_conf["tcp-port"]
        self.joystick_port = self.drone_conf["joystick-port"]
        
        self.vehicle = vehicle
        
        # Durum ve Kontrol Değişkenleri
        self.stop_event = stop_event

        # Hedefler degiskeni
        self.hedefler = {}

        # Nesne Referansları
        self.joystick_handler = None
        self.tcp_client = None
        self.image_handler = None
        self.lidar_handler = None

        #!-------EKLENENLER---------
        self.stop_event = stop_event
        self.hedefler = {}

        # YENİ: Arayüz ile haberleşme için değişkenler
        self.target_name_event = threading.Event()
        self.target_name = None
        self.on_target_detected = None # Callback fonksiyonu
        #!--------------------------

    def baglantilari_kur(self):
        """Tüm donanım, ağ ve yazılım bağlantılarını başlatır."""
        print("[GOZLEMCI]>> Bağlantılar kuruluyor...")

        # 1. Joystick Bağlantısı
        self.joystick_handler = Joystick_Handler(stop_event=self.stop_event, port=self.joystick_port)

        # 2. TCP Bağlantısı (Lidar/Gimbal iletişimi için)
        #TODO: buna stop_event eklenebilir
        self.tcp_client = TCPClient(host=self.rasp_ip, port=self.tcp_port)
        self.tcp_client.connect()

        # 3. Görüntü Aktarımı
        self.image_handler = Image_Handler(stop_event=self.stop_event, window_name="Gozlemci")
        self.image_handler.showing_image = False
        self.image_handler.ters = False
        threading.Thread(target=self.image_handler.udp_camera, 
                         args=(self.rasp_ip, self.udp_port), 
                         daemon=True).start()

        # 4. Lidar Kontrolcüsü
        self.lidar_handler = Lidar_Handler(stop_event=self.stop_event, 
                                           joystick_handler=self.joystick_handler, 
                                           tcp_client=self.tcp_client)
        
        # Video aktarımının başlamasını bekle
        while not self.image_handler.video_started and not self.stop_event.is_set():
            time.sleep(0.05)
        print("[GOZLEMCI]>> Tüm sistem bağlantıları hazır.")

    def kalkis(self):
        """Drone'un GUIDED moda geçmesini bekler, kalkış yapar ve kalkış yönüne hizalanır."""

        self.vehicle.set_mode(mode="GUIDED", drone_id=self.drone_id)
        self.vehicle.arm_disarm(arm=True, drone_id=self.drone_id)
        
        # Kalkış
        self.vehicle.multiple_takeoff(alt=self.alt, drone_id=self.drone_id)
        while not self.stop_event.is_set():
            if abs(self.vehicle.get_pos(drone_id=self.drone_id)[2] - self.alt) <= 0.1:
                break
            time.sleep(0.1)

        print(f"[GOZLEMCI]>> Kalkis tamamlandı. Arama başlatılabilir.")

    #!-------EKLENENLER---------
    def _hedef_koordinat_hesapla(self):
        """Lidar verisini okur ve hedefin mutlak GPS koordinatlarını hesaplar."""
        print("[GOZLEMCI]>> Hedef işaretleme baslatildi")
        while not self.stop_event.is_set():
            lidar_value = self.lidar_handler.get_value()
            
            if lidar_value:
                print(f"[GOZLEMCI]>> Raspberry'den gelen veri: {lidar_value}")
                try:
                    distance, x, y = lidar_value.split("|")
                    distance, x, y = float(distance.strip()), int(x.strip()), int(y.strip())

                    drone_loc = self.vehicle.get_pos(drone_id=self.drone_id)
                    drone_yaw = self.vehicle.get_yaw(drone_id=self.drone_id)
                    drone_pitch = self.vehicle.get_pitch(drone_id=self.drone_id)
                    
                    abs_distance = calc_angle_distance(distance=distance, angle=(drone_pitch + y))
                    hedef_loc = calc_pos(loc=drone_loc, distance=abs_distance, bearing=(drone_yaw + x))

                    print(f"[GOZLEMCI]>> İşaretlenen hedef drone'dan {abs_distance:.2f} metre uzaklıkta.")
                    print(f"[GOZLEMCI]>> Hesaplanan hedeflenen konum: {hedef_loc}")
                    
                    # YENİ: Frontend'e sinyal göndermek için callback tetikle
                    if self.on_target_detected:
                        self.on_target_detected(hedef_loc)

                    # Event'i temizle ve arayüzden gelecek onayı bekle
                    self.target_name_event.clear()
                    self.target_name = None
                    
                    print("[GOZLEMCI]>> Arayüzden hedef adı bekleniyor...")
                    while not self.stop_event.is_set():
                        # Arayüz endpoint'inden event set edilene kadar bekler (timeout ile bloğu kitlemez)
                        if self.target_name_event.wait(timeout=0.5):
                            if self.target_name: # Boş gelmediyse (İptal edilmediyse)
                                hedef_adi = self.target_name
                                self.hedefler[hedef_adi] = hedef_loc
                                print(f"[HEDEFLEME]>> Hedef {hedef_adi} hedeflere eklendi")
                            else:
                                print("[HEDEFLEME]>> Hedef ekleme arayüzden iptal edildi.")
                            break

                except ValueError as e:
                    print(f"[GOZLEMCI]>> Lidar verisi ayrıştırılırken hata oluştu: {e}")
            
            if joystick_value_split(self.joystick_handler.get_value())["joy_btn"]:
                print("[GOZLEMCI]>> Hedef isaretleme tamamlandi")
                break
            
            time.sleep(0.1)
    #!--------------------------

    def gorevi_baslat(self):
        """Gozlemci dronun yapacagi ucus gorevi"""
        try:
            self.kalkis()
            
            # Lidar ile hedefi bekle ve hesapla
            self._hedef_koordinat_hesapla()
            
            self.vehicle.set_mode(mode="LAND", drone_id=self.drone_id)
            #self.vehicle.go_home(alt=self.alt, drone_id=self.drone_id)

            print("[GOZLEMCI]>> Gorevini tamamladi ve guvenli sekilde inis yaptı")
                    
        except Exception as e:
            print(f"[GOZLEMCI]>> Uçuş sırasında hata meydana geldi: {e}")
        except KeyboardInterrupt:
            print("[GOZLEMCI]>> Kullanıcı tarafından uçuş durduruldu (CTRL+C).")