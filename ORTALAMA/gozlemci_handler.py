import threading
import time

from libs.lidar_controller import Lidar_Handler
from libs.joystick_handler import Joystick_Handler
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler
from libs.utils import calc_angle_distance

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe, calc_pos, calc_distance

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

        # Nesne Referansları
        self.joystick_handler = None
        self.tcp_client = None
        self.image_handler = None
        self.lidar_handler = None

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

    def kalkis_ve_hizalama(self):
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

    def _hedef_koordinat_hesapla(self):
        """Lidar verisini okur ve hedefin mutlak GPS koordinatlarını hesaplar."""
        print("[GOZLEMCI]>> Hedef işaretleme bekleniyor (Lidar)...")
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
                    
                    # Hesaplamalar
                    abs_distance = calc_angle_distance(distance=distance, angle=(drone_pitch + y))
                    hedef_loc = calc_pos(loc=drone_loc, distance=abs_distance, bearing=(drone_yaw + x))

                    print(f"[GOZLEMCI]>> İşaretlenen hedef drone'dan {abs_distance:.2f} metre uzaklıkta.")
                    print(f"[GOZLEMCI]>> Hesaplanan hedeflenen konum: {hedef_loc}")
                    print(f"[GOZLEMCI]>> Hedefe olan kuş uçuşu 2D uzaklık: {calc_distance(loc1=hedef_loc, loc2=drone_loc):.2f} metre.")
                    
                    return hedef_loc
                except ValueError as e:
                    print(f"[GOZLEMCI]>> Lidar verisi ayrıştırılırken hata oluştu: {e}")
            
            time.sleep(0.1)
        return None

    def ucus_gorevini_baslat(self):
        """Kalkış, hedef tespit, hedefe gidiş ve dönüş aşamalarını yönetir."""
        try:
            self.kalkis_ve_hizalama()
            
            # Lidar ile hedefi bekle ve hesapla
            hedef_konumu = self._hedef_koordinat_hesapla()
            
            if hedef_konumu is not None and not self.stop_event.is_set():
                print("[GOZLEMCI]>> Hedeflenen konuma gidiliyor...")
                self.vehicle.go_to(loc=hedef_konumu, alt=self.alt, drone_id=self.drone_id)

                while not self.stop_event.is_set() and not self.vehicle.on_location(loc=hedef_konumu, drone_id=self.drone_id):
                    time.sleep(0.5)

                if not self.stop_event.is_set():
                    print("[GOZLEMCI]>> Hedeflenen konuma varıldı. 8 saniye bekleniyor...")
                    time.sleep(8)
                    print("[GOZLEMCI]>> Bekleme süresi bitti. Kalkış konumuna dönülüyor (RTL/Failsafe)...")
                    
        except Exception as e:
            print(f"[GOZLEMCI]>> Uçuş sırasında hata meydana geldi: {e}")
        except KeyboardInterrupt:
            print("[GOZLEMCI]>> Kullanıcı tarafından uçuş durduruldu (CTRL+C).")
        finally:
            self.kapat()

    def kapat(self):
        """Sistemi güvenli şekilde kapatır ve failsafe tetikler."""
        print("[GOZLEMCI]>> Sistem kapatılıyor ve failsafe uygulanıyor...")
        if not self.stop_event.is_set():
            self.stop_event.set()
            
        if self.vehicle:
            failsafe(vehicle=self.vehicle)
            self.vehicle.close()