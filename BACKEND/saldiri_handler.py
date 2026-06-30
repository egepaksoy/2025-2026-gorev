import threading
import time

from libs.utils import gimbal_turn_calculator, gimbal_new_angles
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler
from pymavlink_custom.pymavlink_custom import Vehicle

#? Test edilcek

class Saldiri:
    def __init__(self, vehicle: Vehicle, drone_conf: dict, hedef_siniflari: dict=None, model_path: str=None, stop_event: threading.Event=threading.Event()):
        self.drone_conf = drone_conf

        self.drone_id = self.drone_conf["id"]
        self.alt = self.drone_conf["alt"]
        self.move_speed = self.drone_conf["move-speed"]
        self.rasp_ip = self.drone_conf["rasp-ip"]
        self.udp_port = self.drone_conf["udp-port"]
        self.tcp_port = self.drone_conf["tcp-port"]
        self.conf = self.drone_conf["conf"]
        self.model_path = self.drone_conf["model-path"]
        
        self.yuk1_channel = self.drone_conf["yuk1"]["channel"]
        self.yuk1_kapali = self.drone_conf["yuk1"]["kapali"]
        self.yuk1_acik = self.drone_conf["yuk1"]["acik"]
        
        self.yuk2_channel = self.drone_conf["yuk2"]["channel"]
        self.yuk2_kapali = self.drone_conf["yuk2"]["kapali"]
        self.yuk2_acik = self.drone_conf["yuk2"]["acik"]

        self.aktif_servo_channel = self.yuk1_channel
        self.aktif_servo_acik = self.yuk1_acik
        self.aktif_servo_kapali = self.yuk1_kapali

        if model_path is not None:
            self.model_path = model_path
        self.vehicle = vehicle
        self.stop_event = stop_event
        
        # Hedefleme Değişkenleri
        self.hedef_siniflari = hedef_siniflari # Örn: {"mavi": (konumu)}
        self.aktif_hedef = None
        
        # Gimbal Durum Değişkenleri
        self.gimbal_pos = (90, 90)
        self.gimbal_pos_min = (0, 0)
        self.gimbal_pos_max = (90, 180)
        self.scan_on = False
        self.target_locked = False
        self.gimbal_running = True
        self.gimbal_deadzone = 12
        self.camera_deadzone = 5
        
        # Nesne referansları
        self.image_handler = None
        self.client = None
        self.gimbal_thread = None

    def baglantilari_kur(self):
        """Drone, Gimbal ve Kamera bağlantılarını başlatır."""
        print("[SALDIRI]>> Bağlantılar kuruluyor...")
        
        # 1. Görüntü işleme
        self.image_handler = Image_Handler(stop_event=self.stop_event, window_name="Saldiri")
        self.image_handler.showing_image = False
        self.image_handler.ters = True
        if self.model_path is not None:
            self.image_handler.start_proccessing(model_path=self.model_path, conf=self.conf)
            self.image_handler.conf = self.conf
            print(f"[SALDIRI]>> Goruntu isleme {self.conf} oranıyla {self.model_path} modeli ile baslatildi")
        threading.Thread(target=self.image_handler.udp_camera, args=(self.rasp_ip, self.udp_port), daemon=True).start()

        # 2. Gimbal TCP Bağlantısı
        self.client = TCPClient(host=self.rasp_ip, port=self.tcp_port, stop_event=self.stop_event)
        self.client.connect()
    
        while not self.image_handler.video_started and not self.stop_event.is_set():
            time.sleep(0.5)
        print("[SALDIRI]>> Video aktarımı başarılı.")

        # 3. Gimbal Takip Thread'ini başlat (scan_on True olana kadar beklemede kalır)
        self.gimbal_thread = threading.Thread(target=self._hedef_takip_dongusu, daemon=True)
        self.gimbal_thread.start()
        
        print("[SALDIRI]>> Tüm sistem bağlantıları hazır.")
    
    def kalkis(self):
        """Drone'un kalkış yapmasını sağlar."""
        self.vehicle.set_mode(mode="GUIDED", drone_id=self.drone_id)
        self.vehicle.arm_disarm(arm=True, drone_id=self.drone_id)
        
        self.vehicle.multiple_takeoff(alt=self.alt, drone_id=self.drone_id)
        while not self.stop_event.is_set():
            if abs(self.vehicle.get_pos(drone_id=self.drone_id)[2] - self.alt) <= 0.1:
                break
            time.sleep(0.1)

        print(f"[SALDIRI]>> Kalkis tamamlandı. Arama başlatılabilir.")

    def _hedef_algilandi_mi(self, max_gecikme=2.0):
        """YALNIZCA aktif hedefin algılanıp algılanmadığını kontrol eder."""
        with self.image_handler.object_lock:
            obj = self.image_handler.detected_obj
            # Sınıf adı o anki aktif hedefle eşleşiyor mu kontrolü
            if obj["cls"] == self.aktif_hedef and (time.time() - obj["lt"] < max_gecikme):
                return True
        return False

    def _hedef_takip_dongusu(self):
        """Gimbal'in aktif hedefi taramasını ve kilitlenmesini sağlar."""
        drone_turned = 0
        last_command_time = 0
        # Buradaki sure cok kisilirsa algilamadan hareket ederek kendini bozuyor
        command_interval = 0.5
        
        while not self.stop_event.is_set() and self.gimbal_running:
            if not self.scan_on or self.aktif_hedef is None:
                time.sleep(0.05)
                continue

            current_time = time.time()
            
            if self._hedef_algilandi_mi():
                self.target_locked = True
                drone_turned = 0 
                
                if current_time - last_command_time >= command_interval:
                    with self.image_handler.object_lock:
                        obj = self.image_handler.detected_obj
                        dx, dy = gimbal_turn_calculator(obj["pos"], obj["screen_res"])
                        dx *= -1
                    
                    move_x = dx if abs(dx) > self.camera_deadzone else 0
                    move_y = dy if abs(dy) > self.camera_deadzone else 0
                    
                    self.gimbal_pos = gimbal_new_angles(self.gimbal_pos, (move_y, move_x), 
                                                        self.gimbal_pos_min, self.gimbal_pos_max)
                    
                    self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
                    last_command_time = time.time()
            else:
                self.target_locked = False
                with self.image_handler.object_lock:
                    lt = self.image_handler.detected_obj["lt"] if self.image_handler.detected_obj["lt"] else 0

                if (current_time - lt >= 4.0):
                    self._gimbal_tara()
                    
                    if not self._hedef_algilandi_mi() and drone_turned == 0:
                        old_yaw = self.vehicle.get_yaw(drone_id=self.drone_id)
                        self.vehicle.set_yaw(turn_angle=180, drone_id=self.drone_id)
                        
                        while abs((old_yaw + 180) % 360 - self.vehicle.get_yaw(drone_id=self.drone_id)) > 15:
                            if self.stop_event.is_set(): break
                            time.sleep(0.1)
                        drone_turned += 1
                        
                    elif not self._hedef_algilandi_mi() and drone_turned != 0:
                        print(f"[SALDIRI]>> {self.aktif_hedef} bulunamadı.")
                        self.gimbal_running = False 

            time.sleep(0.05)

    def _gimbal_tara(self):
        """Gimbal'i zigzag patern ile hareket ettirerek aktif hedefi arar."""
        self.gimbal_pos = (90, 90)
        step = 20
        x_min, x_max = self.gimbal_pos_min[1], self.gimbal_pos_max[1] + step

        self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
        
        for y in range(self.gimbal_pos_max[0], self.gimbal_pos_min[0] - 1, -step):
            if self._hedef_algilandi_mi(): break
            self.gimbal_pos = (y, self.gimbal_pos[1])

            if x_min == 0:
                x_min, x_max = self.gimbal_pos_max[1], self.gimbal_pos_min[1] - 1
                step *= -1
            else:
                x_min, x_max = self.gimbal_pos_min[1], self.gimbal_pos_max[1] + 10
                step *= -1

            for x in range(x_min, x_max, step):
                if self._hedef_algilandi_mi(): return
                self.gimbal_pos = (self.gimbal_pos[0], x)
                self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
                
                start_time = time.time()
                while time.time() - start_time <= 0.8:
                    if self._hedef_algilandi_mi(): return
                    if self.stop_event.is_set(): return
                    time.sleep(0.1)

    def _hedefe_ilerle_ve_vur(self):
        """Aktif hedefe kilitlenip ilerler ve konumu bulunca yük bırakır."""
        print(f"[SALDIRI]>> Görev başlatıldı: {self.aktif_hedef} aranıyor...")
        self.scan_on = True
        self.target_locked = False
        obj_pos = None

        while not self.stop_event.is_set():
            if self.target_locked and self._hedef_algilandi_mi():
                # 1. Yük bırakma koşulu (Gimbal tam aşağı bakıyorsa)
                if self.gimbal_pos[0] <= self.gimbal_deadzone:
                    print(f"[SALDIRI]>> {self.aktif_hedef} tam üzerinde! Konum kaydediliyor.")
                    obj_pos = self.vehicle.get_pos(drone_id=self.drone_id)
                    break
                
                # 2. Drone Yaw Ayarı (Gimbal merkeze hizalı değilse)
                yaw_farki = 90 - self.gimbal_pos[1]
                if abs(yaw_farki) > 10:
                    old_yaw = self.vehicle.get_yaw(drone_id=self.drone_id)
                    yaw_acisi = yaw_farki * -1
                    self.vehicle.set_yaw(turn_angle=yaw_acisi, drone_id=self.drone_id)
                    while not self.stop_event.is_set() and abs(self.vehicle.get_yaw(drone_id=self.drone_id) - (old_yaw + yaw_acisi) % 360) > 5:
                        time.sleep(0.05)
                    time.sleep(1.5)

                # 3. İleri Doğru Hareket
                #! Burasi ilerlemesi hic durmasin diye
                speed = (self.move_speed * self.gimbal_pos[0] / 90 + self.move_speed/12)
                self.vehicle.move_drone((speed, 0, 0), drone_id=self.drone_id)

            if not self.gimbal_running:
                print(f"[SALDIRI]>> {self.aktif_hedef} takibi iptal oldu.")
                break
            
            time.sleep(0.1)

        # Hedefe varıldıysa Yük Bırakma
        if obj_pos is not None:
            self.scan_on = False # Yük bırakırken aramayı durdur
            self.vehicle.go_to(loc=obj_pos, drone_id=self.drone_id)

            print(f"[SALDIRI]>> {self.aktif_hedef} kesin lokasyonuna gidiliyor...")
            while not self.vehicle.on_location(loc=obj_pos, drone_id=self.drone_id) and not self.stop_event.is_set():
                time.sleep(0.05)
            
            # Dinamik Servo Tetikleme (yuk_1, yuk_2 vb.)
            self.vehicle.set_servo(channel=self.aktif_servo_channel, pwm=self.aktif_servo_acik, drone_id=self.drone_id)
            self.aktif_servo_channel = self.yuk2_channel
            self.aktif_servo_acik = self.yuk2_acik
            self.aktif_servo_kapali = self.yuk2_kapali
            print(f"[SALDIRI]>> {self.aktif_hedef} için yuk bırakıldı! 5 saniye bekleniyor...")
            time.sleep(5)
            return True
        return False

    def gorevi_baslat(self, hedef_siniflari: dict):
        """Çoklu otonom hedef senaryosunu sırayla işleten ana metod."""
        self.hedef_siniflari = hedef_siniflari
        try:
            self.kalkis()
            time.sleep(2) 

            if not self.hedef_siniflari or len(self.hedef_siniflari) == 0:
                print("[SALDIRI]>> Hedef sınıfı tanımlanmamış, görev iptal.")
                return

            # Tüm hedefleri sırayla gez
            for hedef in self.hedef_siniflari:
                if self.stop_event.is_set(): break
                
                self.aktif_hedef = hedef

                hedef_konumu = self.hedef_siniflari[self.aktif_hedef]

                print(f"[SALDIRI]>> Hedef {self.aktif_hedef} konumuna gidiliyor")
                self.vehicle.go_to(loc=hedef_konumu, alt=self.alt, drone_id=self.drone_id)
                while not self.stop_event.is_set() and not self.vehicle.on_location(loc=hedef_konumu, drone_id=self.drone_id):
                    time.sleep(0.5)
                
                self.gimbal_running = True # Aramayı her yeni hedefte başlat
                
                print(f"[SALDIRI]>> Hedef {self.aktif_hedef} konumuna geldi tarama baslatiliyor")
                basarili = self._hedefe_ilerle_ve_vur()
                
                if not basarili:
                    print(f"[SALDIRI]>> {hedef} vurulamadı, bir sonraki hedefe geçiliyor.")
                
            # Tüm hedefler bitince eve dön
            print("[SALDIRI]>> Tüm hedef operasyonları tamamlandı. Görev sonu, dönüşe geçiliyor.")
            self.gimbal_running = False
            self.vehicle.go_home(alt=self.alt, drone_id=self.drone_id)

        except KeyboardInterrupt:
            print("[SALDIRI]>> \nKullanıcı tarafından uçuş durduruldu!")
            self.kapat()
        except Exception as e:
            print(f"[SALDIRI]>> Görev sırasında hata: {e}")
            self.kapat()

    def kapat(self):
        """Tüm threadleri kapatır ve failsafe uygular."""
        self.gimbal_running = False
        self.scan_on = False