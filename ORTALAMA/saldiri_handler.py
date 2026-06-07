import threading
import time
import json

from libs.utils import gimbal_turn_calculator, gimbal_new_angles
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler
from pymavlink_custom.pymavlink_custom import Vehicle, failsafe

class Saldiri:
    def __init__(self, vehicle: Vehicle, drone_conf: dict, model_path: str=None, stop_event: threading.Event=threading.Event()):
        self.drone_conf = drone_conf

        self.drone_id = self.drone_conf["id"]
        self.alt = self.drone_conf["alt"]
        self.move_speed = self.drone_conf["move-speed"]
        self.rasp_ip = self.drone_conf["rasp-ip"]
        self.udp_port = self.drone_conf["udp-port"]
        self.tcp_port = self.drone_conf["tcp-port"]
        self.conf = self.drone_conf["conf"]

        self.model_path = model_path

        self.vehicle = vehicle
        
        # Durum değişkenleri
        self.stop_event = stop_event
        self.gimbal_pos = (90, 90)
        self.gimbal_pos_min = (0, 0)
        self.gimbal_pos_max = (90, 180)
        self.scan_on = False
        self.target_locked = False
        self.gimbal_running = True
        self.gimbal_deadzone = 10
        self.camera_deadzone = 5
        
        # Nesne referansları
        self.image_handler = None
        self.client = None
        self.gimbal_thread = None


    def baglantilari_kur(self):
        """Drone, Gimbal ve Kamera bağlantılarını başlatır."""
        print("[SALDIRI]>> Bağlantılar kuruluyor...")
        
        # 1. Görüntü işleme thread'i
        self.image_handler = Image_Handler(stop_event=self.stop_event, window_name="Saldiri")

        # Görüntü İşleme Ayarları
        self.image_handler.start_proccessing(model_path=self.model_path)
        self.image_handler.conf = self.conf
        threading.Thread(target=self.image_handler.udp_camera, 
                         args=(self.rasp_ip, self.udp_port), 
                         daemon=True).start()

        # 2. Gimbal TCP Bağlantısı
        #TODO: buna stop_event eklenebilir
        self.client = TCPClient(host=self.rasp_ip, port=self.tcp_port)
        self.client.connect()
    
        # Kameranın açılmasını bekle
        while not self.image_handler.video_started and not self.stop_event.is_set():
            time.sleep(0.5)
        print("[SALDIRI]>> Video aktarımı başarılı.")

        # 3. Gimbal Takip Thread'ini başlat (scan_on True olana kadar beklemede kalır)
        self.gimbal_thread = threading.Thread(target=self._hedef_takip_dongusu, daemon=True)
        self.gimbal_thread.start()
        
        print("[SALDIRI]>> Tüm sistem bağlantıları hazır.")

    def _hedef_algilandi_mi(self, max_gecikme=1.0):
        """Hedefin anlık olarak algılanıp algılanmadığını kontrol eder."""
        with self.image_handler.object_lock:
            obj = self.image_handler.detected_obj
            if obj["cls"] is not None and (time.time() - obj["lt"] < max_gecikme):
                return True
        return False

    def _hedef_takip_dongusu(self):
        """Gimbal'in hedefi taramasını ve kilitlenmesini sağlayan arka plan görevi."""
        drone_turned = 0
        last_command_time = 0
        command_interval = 0.05
        
        while not self.stop_event.is_set() and self.gimbal_running:
            if not self.scan_on:
                time.sleep(0.05)
                continue

            current_time = time.time()
            
            # Hedef Algılandıysa Takip Et
            if self._hedef_algilandi_mi(max_gecikme=1.0):
                self.target_locked = True
                drone_turned = 0 # Hedef bulundu, dönüş sayacını sıfırla
                
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
                    
            # Hedef Kayıpsa veya Hiç Bulunmadıysa Tara
            else:
                self.target_locked = False
                # Hedef uzun süredir (4sn) yoksa tarama moduna geç
                with self.image_handler.object_lock:
                    lt = self.image_handler.detected_obj["lt"]
                    is_none = self.image_handler.detected_obj["cls"] is None

                if is_none or (current_time - lt >= 4.0):
                    print("[SALDIRI]>> Hedef aranıyor/kayboldu, tarama moduna geçiliyor...")
                    self._gimbal_tara()
                    
                    # Taramadan sonra hala yoksa Drone'u döndür
                    if not self._hedef_algilandi_mi() and drone_turned == 0:
                        print("[SALDIRI]>> Hedef bulunamadı, drone 180 derece dönüyor.")
                        old_yaw = self.vehicle.get_yaw(drone_id=self.drone_id)
                        self.vehicle.set_yaw(turn_angle=180, drone_id=self.drone_id)
                        
                        while abs((old_yaw + 180) % 360 - self.vehicle.get_yaw(drone_id=self.drone_id)) > 15:
                            if self.stop_event.is_set(): break
                            time.sleep(0.1)
                        drone_turned += 1
                        print("[SALDIRI]>> Dönüş tamamlandı.")
                        
                    elif not self._hedef_algilandi_mi() and drone_turned != 0:
                        print("[SALDIRI]>> Tüm taramalara rağmen hedef bulunamadı.")
                        self.gimbal_running = False # İsteğe bağlı: Aramayı tamamen kes

            time.sleep(0.05)

    def _gimbal_tara(self):
        """Gimbal'i belirli bir patern ile hareket ettirerek hedef arar."""
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
                if self._hedef_algilandi_mi():
                    print("[SALDIRI]>> Tarama sırasında hedef bulundu!")
                    return

                self.gimbal_pos = (self.gimbal_pos[0], x)
                self.client.send_data(f"{self.gimbal_pos[0]}|{self.gimbal_pos[1]}")
                
                # Gimbal hareketinin gerçekleşmesi için kısa bekleme
                start_time = time.time()
                while time.time() - start_time <= 0.8:
                    if self._hedef_algilandi_mi(): return
                    time.sleep(0.1)

    #TODO: Bu kod iki adet hedefi alıp o hedeflere gitme yapılcak
    def ucus_ve_saldiri_baslat(self):
        """Bağlantılar kurulduktan sonra uçuş görevini başlatır."""
        try:
            print("[SALDIRI]>> Uçuş başlıyor!")
            self.vehicle.set_mode(mode="GUIDED", drone_id=self.drone_id)
            self.vehicle.arm_disarm(arm=True, drone_id=self.drone_id)
            self.vehicle.multiple_takeoff(alt=self.alt, drone_id=self.drone_id)

            print("[SALDIRI]>> Takeoff alınıyor...")
            start_time = time.time()
            while not self.stop_event.is_set():
                pos = self.vehicle.get_pos(drone_id=self.drone_id)
                if pos[2] > self.alt * 0.9:
                    break
                if time.time() - start_time >= 2:
                    print(f"[SALDIRI]>> Mevcut İrtifa: {pos[2]}")
                    start_time = time.time()
                time.sleep(0.5)
                
            print("[SALDIRI]>> Takeoff tamamlandı.")
            
            # Tarama ve hedef takibi aktif ediliyor
            self.scan_on = True
            time.sleep(2) # Sistemin oturması için kısa bir süre bekle

            obj_pos = None

            # Görev Döngüsü
            while not self.stop_event.is_set():
                if self.target_locked and self._hedef_algilandi_mi():
                    # 1. Yük bırakma koşulu (Gimbal tam aşağı bakıyorsa)
                    if self.gimbal_pos[0] <= self.gimbal_deadzone:
                        print("[SALDIRI]>> Hedefin tam üzerinde! Konum kaydediliyor.")
                        obj_pos = self.vehicle.get_pos(drone_id=self.drone_id)
                        break
                    
                    # 2. Drone Yaw Ayarı (Gimbal merkeze hizalı değilse)
                    yaw_farki = 90 - self.gimbal_pos[1]
                    if abs(yaw_farki) > 10:
                        old_yaw = self.vehicle.get_yaw(drone_id=self.drone_id)
                        yaw_acisi = yaw_farki * -1 # Ters dönme düzeltmesi
                        print(f"[SALDIRI]>> Döndürülecek yaw açısı: {yaw_acisi}")
                        
                        self.vehicle.set_yaw(turn_angle=yaw_acisi, drone_id=self.drone_id)
                        while not self.stop_event.is_set() and abs(self.vehicle.get_yaw(drone_id=self.drone_id) - (old_yaw + yaw_acisi) % 360) > 5:
                            time.sleep(0.05)
                        time.sleep(1.5) # Manevra sonrası stabilizasyon

                    # 3. İleri Doğru Hareket (Gimbal aşağı baktıkça hız düşer)
                    speed = (self.move_speed * self.gimbal_pos[0] / 90)
                    print(f"[SALDIRI]>> {speed:.2f} hızında hedefe ilerleniyor. Gimbal Pitch: {self.gimbal_pos[0]}")
                    self.vehicle.move_drone((speed, 0, 0), drone_id=self.drone_id)

                if not self.gimbal_thread.is_alive():
                    print("[SALDIRI]>> Gimbal takip sistemi durdu, görev iptal ediliyor.")
                    break
                
                time.sleep(0.1)

            # Hedef konumuna varıldıysa Yük Bırakma
            if obj_pos is not None:
                self.gimbal_running = False
                self.vehicle.go_to(loc=obj_pos, drone_id=self.drone_id)

                print("[SALDIRI]>> Hedefin kesin lokasyonuna gidiliyor...")
                while not self.vehicle.on_location(loc=obj_pos, drone_id=self.drone_id) and not self.stop_event.is_set():
                    time.sleep(0.05)
                
                self.vehicle.set_servo(channel=self.drone_conf["servo"]["channel"], 
                                       pwm=self.drone_conf["servo"]["yuk_1"], 
                                       drone_id=self.drone_id)
                
                print("[SALDIRI]>> Yük bırakıldı! 5 saniye bekleniyor...")
                time.sleep(5)
                print("[SALDIRI]>> Görev tamamlandı, dönüşe geçiliyor.")
            else:
                print("[SALDIRI]>> Hedef konumu alınamadı, görev başarısız.")

            failsafe(vehicle=self.vehicle)

        except KeyboardInterrupt:
            print("[SALDIRI]>> \nKullanıcı tarafından uçuş durduruldu!")
            self.kapat()

    def kapat(self):
        """Tüm threadleri kapatır ve failsafe uygular."""
        self.gimbal_running = False
        self.scan_on = False
        if not self.stop_event.is_set():
            self.stop_event.set()
        
        if self.vehicle:
            failsafe(self.vehicle)