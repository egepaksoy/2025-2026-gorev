import threading
import time

from libs.utils import gimbal_turn_calculator, gimbal_new_angles
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler
from pymavlink_custom.pymavlink_custom import Vehicle, calc_pos
import math

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
        self.gimbal_pos = (70, 90)
        self.gimbal_pos_min = (0, 0)
        self.gimbal_pos_max = (70, 180)
        self.gimbal_deadzone = 13
        self.camera_deadzone = 5
        
        # Nesne referansları
        self.image_handler = None
        self.client = None
        self.gimbal_thread = None

        # yaw dondurme
        self.yaw_turning = False

    def baglantilari_kur(self):
        """Drone, Gimbal ve Kamera bağlantılarını başlatır."""
        print("[SALDIRI]>> Bağlantılar kuruluyor...")
        
        # 1. Görüntü işleme
        self.image_handler = Image_Handler(stop_event=self.stop_event, window_name="Saldiri")
        # self.image_handler.showing_image = False
        # TODO: Burayı kaldır
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
        
        print("[SALDIRI]>> Tüm sistem bağlantıları hazır.")
    
    def kalkis(self):
        """Drone'un kalkış yapmasını sağlar."""
        print("Saldiri kalkis")
        self.vehicle.set_mode(mode="GUIDED", drone_id=self.drone_id)
        time.sleep(1)
        print("arm aliyor")
        self.vehicle.arm_disarm(arm=True, drone_id=self.drone_id)
        time.sleep(1)
        
        print("takeoff aliyor")
        self.vehicle.multiple_takeoff(alt=self.alt, drone_id=self.drone_id)
        while not self.stop_event.is_set():
            if abs(self.vehicle.get_pos(drone_id=self.drone_id)[2] - self.alt) <= 0.1:
                break
            time.sleep(0.1)

        print(f"[SALDIRI]>> Kalkis tamamlandı. Arama başlatıldı.")

    def _hedef_algilandi_mi(self, max_gecikme=1.2):
        """YALNIZCA aktif hedefin algılanıp algılanmadığını kontrol eder."""
        with self.image_handler.object_lock:
            obj = self.image_handler.detected_obj
            # Sınıf adı o anki aktif hedefle eşleşiyor mu kontrolü
            if obj["cls"] == self.aktif_hedef and (time.time() - obj["lt"] < max_gecikme):
                return True
        return False

    def _gimbal_tara(self):
        """Gimbal'i zigzag patern ile hareket ettirerek aktif hedefi arar."""
        self.gimbal_pos = (90, 90)
        step = 20
        x_min, x_max = self.gimbal_pos_min[1], self.gimbal_pos_max[1] + step

        self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
        
        #! Burası degisti
        for y in range(self.gimbal_pos_max[0], self.gimbal_pos_min[0] - 1, -step):
            if self._hedef_algilandi_mi(): return True
            if self.stop_event.is_set(): return False
            self.gimbal_pos = (y, self.gimbal_pos[1])

            if x_min == 0:
                x_min, x_max = self.gimbal_pos_max[1], self.gimbal_pos_min[1] - 1
                step *= -1
            else:
                x_min, x_max = self.gimbal_pos_min[1], self.gimbal_pos_max[1] + 10
                step *= -1

            for x in range(x_min, x_max, step):
                if self._hedef_algilandi_mi(): return True
                if self.stop_event.is_set(): return False
                self.gimbal_pos = (self.gimbal_pos[0], x)
                self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
                
                start_time = time.time()
                while time.time() - start_time <= 1:
                    if self._hedef_algilandi_mi(): return True
                    if self.stop_event.is_set(): return False
                    time.sleep(0.05)

        return False

    def _gimbal_lock(self, lock_stopper: threading.Event=threading.Event()):
        """Gimbal'in aktif hedefi taramasını ve kilitlenmesini sağlar."""        
        while not self.stop_event.is_set() and not lock_stopper.is_set():
            if self._hedef_algilandi_mi():
                obj = self.image_handler.detected_obj
                dx, dy = gimbal_turn_calculator(obj["pos"], obj["screen_res"])
                dx *= -1

                move_x = dx if abs(dx) > self.camera_deadzone else 0
                move_y = dy if abs(dy) > self.camera_deadzone else 0

                move_x *= 0.8
                move_y *= 0.8

                self.gimbal_pos = gimbal_new_angles(self.gimbal_pos, (move_y, move_x), 
                                                    self.gimbal_pos_min, self.gimbal_pos_max)

                self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")

            time.sleep(0.5)
        print("Servo kilitlenme sistemi durduruldu")

    def _hedefe_git(self, drone_dondur: bool=True):
        bulundu = self._gimbal_tara()

        if self.stop_event.is_set():
            return False

        if bulundu:
            print(f"Hedef {self.aktif_hedef} taramada bulundu")

            lock_stopper = threading.Event()
            threading.Thread(target=self._gimbal_lock, args=(lock_stopper, ), daemon=True).start()

            print(f"Drone hedefe yonlendiriliyor")
            yaw_angle = 90 - self.gimbal_pos[1]
            self.vehicle.set_yaw(turn_angle=yaw_angle, default_speed=30, drone_id=self.drone_id)

            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time < 5:
                time.sleep(0.05)

            if not self._hedef_algilandi_mi():
                print(f"{self.aktif_hedef} kayboldu tekrar tarama yapılıyor")
                return self._hedefe_git(drone_dondur=True)
            
            print(f"Drone hedefe donduruldu")

            yaw_angle = 90 - self.gimbal_pos[1]
            if abs(yaw_angle) > 8:
                print(f"İnce ayar yapılıyor")
                self.vehicle.set_yaw(turn_angle=yaw_angle, default_speed=30, drone_id=self.drone_id)

                start_time = time.time()
                while not self.stop_event.is_set() and time.time() - start_time < 5:
                    time.sleep(0.05)

            aci_radyan = math.radians(self.vehicle.get_pitch(drone_id=self.drone_id) + self.gimbal_pos[0])
            hedef_mesafe = self.vehicle.get_pos(drone_id=self.drone_id)[2] * math.tan(aci_radyan)

            hedef_mesafe *= 0.9

            hedef_pos = calc_pos(loc=self.vehicle.get_pos(drone_id=self.drone_id), distance=hedef_mesafe, bearing=self.gimbal_pos[1])

            self.vehicle.go_to(loc=hedef_pos, alt=self.alt, drone_id=self.drone_id)
            while not self.stop_event.is_set():
                if self.vehicle.on_location(loc=hedef_pos, drone_id=self.drone_id): break
                time.sleep(0.1)

            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time < 1:
                time.sleep(0.05)

            print(f"Hedef konumuna geldi yuk bırakılıyor")
            self.vehicle.set_servo(channel=self.aktif_servo_channel, pwm=self.aktif_servo_acik, drone_id=self.drone_id)
            time.sleep(1)
            self.vehicle.set_servo(channel=self.aktif_servo_channel, pwm=self.aktif_servo_kapali, drone_id=self.drone_id)
            time.sleep(1)

            lock_stopper.set()
            return True

        else:
            if not drone_dondur:
                print(f"Hedef {self.aktif_hedef} bulunamadı")
                return False

            print(f"Hedef {self.aktif_hedef} taramada bulunmadı. Drone 180 derece donduruluyor")
            self.vehicle.set_yaw(turn_angle=180, drone_id=self.drone_id)

            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time < 10:
                time.sleep(0.05)
            return self._hedefe_git(drone_dondur=False)


    def gorevi_baslat(self, hedef_siniflari: dict):
        """Çoklu otonom hedef senaryosunu sırayla işleten ana metod."""
        self.hedef_siniflari = hedef_siniflari
        if not self.hedef_siniflari or len(self.hedef_siniflari) == 0:
            print("[SALDIRI]>> Hedef sınıfı tanımlanmamış, görev iptal.")
            return

        self.kalkis()
        time.sleep(2)

        # Tüm hedefleri sırayla gez
        for hedef in self.hedef_siniflari:
            if self.stop_event.is_set(): break
            
            self.aktif_hedef = hedef

            hedef_konumu = self.hedef_siniflari[self.aktif_hedef]

            print(f"[SALDIRI]>> Hedef {self.aktif_hedef} konumuna gidiliyor")
            self.vehicle.go_to(loc=hedef_konumu, alt=self.alt, drone_id=self.drone_id)
            while not self.stop_event.is_set() and not self.vehicle.on_location(loc=hedef_konumu, drone_id=self.drone_id):
                time.sleep(0.5)

            # Hedefe varınca 2 sn bekleme
            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time <= 2:
                time.sleep(0.05)

            print(f"[SALDIRI]>> Hedef {self.aktif_hedef} konumuna geldi tarama baslatiliyor")
            sonuc = self._hedefe_git()

            if sonuc:
                print(f"Hedef {self.aktif_hedef} basariyla imha edildi")
            
            self.aktif_servo_channel = self.yuk2_channel
            self.aktif_servo_acik = self.yuk2_acik
            self.aktif_servo_kapali = self.yuk2_kapali

        if not self.stop_event.is_set():
            # Tüm hedefler bitince eve dön
            print("[SALDIRI]>> Tüm hedef operasyonları tamamlandı. Görev sonu, dönüşe geçiliyor.")

            print(f"{self.drone_id} idli saldiri dronu kalkis konumuna donuyor")
            self.vehicle.set_mode(mode="GUIDED", drone_id=self.drone_id)
            time.sleep(1)
            takeoff_pos = self.vehicle.get_home_pos(drone_id=self.drone_id)
            self.vehicle.go_to(loc=takeoff_pos, alt=self.alt, drone_id=self.drone_id)

            while not self.stop_event.is_set() and not self.vehicle.on_location(loc=takeoff_pos, drone_id=self.drone_id):
                time.sleep(0.1)

            print(f"{self.drone_id} idli saldiri dronu kalkis konumuna dondu LAND alıyor")
            self.vehicle.set_mode(mode="LAND", drone_id=self.drone_id)
            time.sleep(1)

        else:
            print("Gorev iptal edildi")