# Gimbal hedef takibi
import threading
import time
import json

from libs.utils import gimbal_turn_calculator, gimbal_new_angles
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler
from pymavlink_custom.pymavlink_custom import Vehicle


def hedef_takip(vehicle: Vehicle, client: TCPClient, stop_event: threading.Event, detected_obj: dict, detect_lock: threading.Lock, recrsv: bool = False):
    DEADZONE = 5
    #          y ,  x
    global gimbal_pos
    global scan_on
    global target_locked
    global gimbal_running

    if recrsv:
        print("Recursive fonksiyona girildi")
    lost = False
    detected = False
    drone_turned = 0

    while not stop_event.is_set() and scan_on == False:
        time.sleep(0.05)

    with detect_lock:
        if detected_obj["cls"] is not None:
            detected = True
        else:
            print("Hedef arama başlatıldı")

    while not detected and drone_turned <= 1 and gimbal_running:
        gimbal_pos = (90, 90)
        gimbal_pos_min = (0, 0)
        gimbal_pos_max = (90, 180)

        step = 20
        x_min = gimbal_pos_min[1]
        x_max = gimbal_pos_max[1] + step

        client.send_data(f"{gimbal_pos[0]}|{gimbal_pos[1]}")
        for y in range(gimbal_pos_max[0], gimbal_pos_min[0]-1, -1*step):
            if detected:
                break
            gimbal_pos = (y, gimbal_pos[1])

            if x_min == 0:
                x_min = gimbal_pos_max[1]
                x_max = gimbal_pos_min[1]-1
                step *= -1
            else:
                x_min = gimbal_pos_min[1]
                x_max = gimbal_pos_max[1] + 10
                step *= -1

            for x in range(x_min, x_max, step):
                with detect_lock:
                    if detected_obj["cls"] is not None:
                        print(f"{detected_obj['cls']} bulundu")
                        detected = True
                        break

                gimbal_pos = (gimbal_pos[0], x)

                client.send_data(f"{gimbal_pos[0]}|{gimbal_pos[1]}")
                start_time = time.time()
                while time.time() - start_time <= 0.8:
                    time.sleep(0.1)

        if not detected and drone_turned == 0:
            if vehicle is not None:
                old_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
                vehicle.set_yaw(turn_angle=180, drone_id=DRONE_ID)
                print("Drone 180 derece donuyor")
                while abs((old_yaw + 180) % 360 - vehicle.get_yaw(drone_id=DRONE_ID)) > 15:
                    time.sleep(0.1)
            drone_turned += 1
            print("Drone 180 derece dondu")
        
        elif not detected and drone_turned != 0:
            break
    
    if not detected:
        print("Hedef bulunamadı")
        return False
    
    if recrsv:
        return True


    last_command_time = 0
    command_interval = 0.05 # Komut gönderme sıklığı (saniye)

    centered = False

    print("Hedefe kitleniyor")
    while not stop_event.is_set() and gimbal_running:
        current_time = time.time()
        
        # Belirli aralıklarla komut gönder (Arduino'yu boğmamak için)
        if current_time - last_command_time >= command_interval:
            dx, dy = 0, 0
            target_found = False

            with detect_lock:
                # Hedef algılandı mı ve veri güncel mi? (son 0.5 sn)
                if detected_obj["cls"] is not None and (current_time - detected_obj["lt"] < 1):
                    dx, dy = gimbal_turn_calculator(detected_obj["pos"], detected_obj["screen_res"])
                    dx *= -1
                    target_found = True
                    
            if detected_obj["cls"] is None and (current_time - detected_obj["lt"] >= 4):
                target_locked = False
                print("Hedef kayblodu tekrar taramaya geciliyor")
                hedef_bulundu = hedef_takip(vehicle, client, stop_event, detected_obj, detect_lock, recrsv=True)
                if not hedef_bulundu:
                    print("Taramadan cikildi")
                    return False

            
            if target_found:
                # Deadzone kontrolü
                move_x = dx if abs(dx) > DEADZONE else 0
                move_y = dy if abs(dy) > DEADZONE else 0

                gimbal_pos = gimbal_new_angles(gimbal_pos, (move_y, move_x), gimbal_pos_min, gimbal_pos_max)

                client.send_data(f"{gimbal_pos[0]}|{gimbal_pos[1]}")
                print(gimbal_pos)
                
                start_time = time.time()
                while not stop_event.is_set() and time.time() - start_time < 1:
                    time.sleep(0.1)

                target_locked = True
                    
                last_command_time = current_time

        time.sleep(0.05)

# Program degiskenleri
stop_event = threading.Event()
drone_conf = json.load(open("./drone_conf.json", "r"))

# Gimbal kontrolu icin degiskenler
gimbal_pos = (90, 90)
scan_on = True
target_locked = False
gimbal_running = True

RASP_IP = drone_conf["rasp-ip"]
UDP_PORT = drone_conf["camera-port"]
TCP_PORT = drone_conf["gimbal-port"]

# Goruntu isleme icin degiskenler
img_handler = Handler(stop_event=stop_event)
img_handler.start_proccessing(model_path="./models/ates_post.pt")
img_handler.conf = 0.9
detected_obj = {
     "cls": None,
     "pos": None,
     "dist": None,
     "lt": None,
     "screen_res": None
}
detected_lock = threading.Lock()

# Goruntu isleme threadi
threading.Thread(target=img_handler.udp_camera, args=(RASP_IP, UDP_PORT, detected_obj, detected_lock), daemon=True).start()

# Gimbal baglantisi
client = TCPClient(host=RASP_IP, port=TCP_PORT)
client.connect()

while not img_handler.video_started:
    time.sleep(0.5)

print("Video aktarımı basarili")

# Gimbal ile hedefi bulma
gimbal_thread = threading.Thread(target=hedef_takip, args=(None, client, stop_event, detected_obj, detected_lock, False), daemon=True)
gimbal_thread.start()

DRONE_ID = drone_conf["id"]

try:
    while not stop_event.is_set():
        time.sleep(0.5)

except KeyboardInterrupt:
    print("Koddan cikildi")
    gimbal_running = False

    if not stop_event.is_set():
        stop_event.set()