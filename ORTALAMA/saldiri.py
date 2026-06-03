# Drone ile hedefe ilerleme kodu
#? Test edilcek
import threading
import time
import json

from libs.utils import gimbal_turn_calculator, gimbal_new_angles
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe


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
scan_on = False
target_locked = False
gimbal_running = True

RASP_IP = drone_conf["rasp-ip"]
UDP_PORT = drone_conf["camera-port"]
TCP_PORT = drone_conf["gimbal-port"]

# Goruntu isleme icin degiskenler
img_handler = Handler(stop_event=stop_event)
img_handler.start_proccessing(model_path="./models/maviaraba.pt")
img_handler.conf = 0.9

gimbal_deadzone = 10

# Goruntu isleme threadi
threading.Thread(target=img_handler.udp_camera, args=(RASP_IP, UDP_PORT), daemon=True).start()

# Gimbal baglantisi
client = TCPClient(host=RASP_IP, port=TCP_PORT)
client.connect()

while not img_handler.video_started:
    time.sleep(0.5)

print("Video aktarımı basarili")

vehicle = Vehicle(address=drone_conf["address"], stop_event=stop_event)

# Gimbal ile hedefi bulma
gimbal_thread = threading.Thread(target=hedef_takip, args=(vehicle, client, stop_event, img_handler.detected_obj, img_handler.object_lock, False), daemon=True)
gimbal_thread.start()

DRONE_ID = drone_conf["id"]
ALT = drone_conf["alt"]

MOVE_SPEED = drone_conf["move-speed"]

try:
    input("Servo kapatilmasi icin yuku yerlestirin sonrasinda enter'a basin")

    print("Ucus basliyor")
    vehicle.set_mode(mode="GUIDED", drone_id=DRONE_ID)
    vehicle.arm_disarm(arm=True, drone_id=DRONE_ID)
    vehicle.multiple_takeoff(alt=ALT, drone_id=DRONE_ID)

    print("TAKEOFF ALIYOR")
    start_time = time.time()
    while not stop_event.is_set() and vehicle.get_pos(drone_id=DRONE_ID)[2] <= ALT * 0.9:
        if time.time() - start_time >= 2:
            print(vehicle.get_pos(drone_id=DRONE_ID))
            start_time = time.time()
        time.sleep(0.5)
    print("TAKEOFF TAMAMLANDI")
    
    scan_on = True

    start_time = time.time()
    while not stop_event.is_set() and time.time() - start_time < 3:
        time.sleep(0.1)

    # hedefin algilandigini algilayip ilerleme kismi
    with img_handler.object_lock:
        detected_obj_cpy = img_handler.detected_obj
    obj_pos = None
    while not stop_event.is_set():
        with img_handler.object_lock:
            if img_handler.detected_obj["cls"] is not None:
                detected_obj_cpy = img_handler.detected_obj
        
        if target_locked:
            print(f"Gimbal Acisi: {gimbal_pos}")
            if detected_obj_cpy["cls"] is not None:
                # nesne algilandi ise ve gimbal asagi bakiyorsa
                if gimbal_pos[0] <= gimbal_deadzone and target_locked:
                    print("Hedefin uzerinde konumu alinip gidiliyor")
                    obj_pos = vehicle.get_pos(drone_id=DRONE_ID)
                    break
            
                # Gimbalin 180 derecesi dronun sagına denk geliyor
                # 5 derece açısı olmayabilir daha buyuk bir aci gerekebilir yoksa surekli yaw ayarlar
                if abs(90 - gimbal_pos[1]) > 10:
                    old_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
                    # TODO: drone ucusta terse donuyordu onu duzeltme
                    yaw_acisi = (90 - gimbal_pos[1]) * -1
                    print(f"Dondurulecek yaw acisi: {yaw_acisi}")
                    vehicle.set_yaw(turn_angle=yaw_acisi, drone_id=DRONE_ID)

                    while not stop_event.is_set() and abs(vehicle.get_yaw(drone_id=DRONE_ID) - (old_yaw + yaw_acisi) % 360) > 5:
                        time.sleep(0.05)
                    
                    start_time = time.time()
                    while not stop_event.is_set() and time.time() - start_time < 1.5:
                        time.sleep(0.1)

                # nesne algilandi ise hizi dusurerek ilerleme
                speed = (MOVE_SPEED * gimbal_pos[0] / 90)
                print(f"{speed} hızında nesneye ilerleniyor")
                vehicle.move_drone((speed, 0, 0), drone_id=DRONE_ID)
        
        if not gimbal_thread.is_alive():
            break
    
        time.sleep(0.1)

    if obj_pos is not None:
        gimbal_running = False
        vehicle.go_to(loc=obj_pos, drone_id=DRONE_ID)

        print("Hedefin uzerine gidiyor")
        while not vehicle.on_location(loc=obj_pos, drone_id=DRONE_ID) and not stop_event.is_set():
            time.sleep(0.05)
        
        vehicle.set_servo(channel=drone_conf["servo"]["channel"], pwm=drone_conf["servo"]["yuk_1"], drone_id=DRONE_ID)
        
        print("Hedefe yuk birakildi 5 sn bekleniyor")
        start_time = time.time()
        while not stop_event.is_set() and time.time() - start_time <= 5:
            time.sleep(0.1)
        
        print("Yuk birakildi donuyor")

    else:
        print("Obj_pos none")

    failsafe(vehicle=vehicle)

except KeyboardInterrupt:
    print("Koddan cikildi")
    gimbal_running = False

    failsafe(vehicle)
    
    if not stop_event.is_set():
        stop_event.set()