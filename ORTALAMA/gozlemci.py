# Gozlemci drone lidar kontrollu hedef isaretleme ve gitme kodu
#? Test basarili ucusda denencek
from libs.lidar_controller import Lidar_Handler
from libs.joystick_handler import Joystick_Handler
from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler as Image_Handler

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe

from libs.utils import calc_angle_distance
from pymavlink_custom.pymavlink_custom import calc_pos, calc_distance

import threading, time

stop_event = threading.Event()

# Degiskenler
RASP_IP = "192.168.0.120"
TCP_PORT = 5005
UDP_PORT = 9999
JOYSTICK_COM_PORT = "COM15"
DRONE_ID = 1
ALT = 5
#VEHICLE_ADDR = "COM6"
VEHICLE_ADDR = "udp:172.22.160.1:14550"


# Joystick baglantı ve baglantı testi
joystick_handler = Joystick_Handler(stop_event=stop_event, port=JOYSTICK_COM_PORT)

# TCP Baglantı ve baglantı testi
tcp_client = TCPClient(host=RASP_IP, port=TCP_PORT)

# Goruntu aktarma kısmı
image_handler = Image_Handler(stop_event=stop_event)
image_handler.ters = False
threading.Thread(target=image_handler.udp_camera, args=(RASP_IP, UDP_PORT), daemon=True).start()

while not image_handler.video_started:
    time.sleep(0.05)
print("[TESTED]>> Video aktarımı basarili")

# Lidar kontrolcusu
lidar_handler = Lidar_Handler(stop_event=stop_event, joystick_handler=joystick_handler, tcp_client=tcp_client)

# Drone baglantısı
vehicle = Vehicle(address=VEHICLE_ADDR, stop_event=stop_event)

while not stop_event.is_set():
    inp = input("Eger ucusa hazirsa Y'ye basin cikis icin ex yazin: ")
    if inp.strip() == "Y":
        break
    if inp.strip() == "ex":
        exit(1)

try:
    #? Mode GUIDED beklemesi
    print(f"{DRONE_ID}>> Mode GUIDED alinmasi bekleniyor")
    while not stop_event.is_set():
        if vehicle.get_mode(drone_id=DRONE_ID) == "GUIDED":
            break
        time.sleep(0.05)
    print(f"{DRONE_ID}>> Mode GUIDED yapildi TAKEOFF aliniyor")

    #? Takeoff
    takeoff_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
    print("Kalkis oncesi drone yaw'i: ", takeoff_yaw)
    vehicle.multiple_takeoff(alt=ALT, drone_id=DRONE_ID)
    while not stop_event.is_set():
        if abs(vehicle.get_pos(drone_id=DRONE_ID)[2] - ALT) <= 0.1:
            break

    #? Dronu kalkis yonune dondurme
    print(f"{DRONE_ID}>> Takeoff tamamlandi drone kalkis yonune donduruluyor")
    vehicle.set_yaw(turn_angle=takeoff_yaw, relative=False, drone_id=DRONE_ID)
    print(f"aradaki yaw farki: {abs(takeoff_yaw - vehicle.get_yaw(drone_id=DRONE_ID))%360}\nDrone yaw: {vehicle.get_yaw(drone_id=DRONE_ID)}")
    start_time = time.time()
    while abs(takeoff_yaw - vehicle.get_yaw(drone_id=DRONE_ID))%360 > 5:
        time.sleep(0.05)
        if time.time() - start_time > 1:
            start_time = time.time()
            print(f"aradaki yaw farki: {abs(takeoff_yaw - vehicle.get_yaw(drone_id=DRONE_ID))%360}\nDrone yaw: {vehicle.get_yaw(drone_id=DRONE_ID)}")
    print(f"aradaki yaw farki: {abs(takeoff_yaw - vehicle.get_yaw(drone_id=DRONE_ID))%360}\nDrone yaw: {vehicle.get_yaw(drone_id=DRONE_ID)}")

    print(f"{DRONE_ID}>> Drone yonu kalkis yonune getirildi arama basladi")
    
    loc = None

    while not stop_event.is_set():
        lidar_value = lidar_handler.get_value()
        if lidar_value:
            print(f"Raspberryden gelen veri: {lidar_value}")
            distance, x, y = lidar_value.split("|")

            drone_loc = vehicle.get_pos(drone_id=DRONE_ID)
            drone_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
            drone_pitch = vehicle.get_pitch(drone_id=DRONE_ID)
            
            abs_distance = calc_angle_distance(distance=float(distance.strip()), angle=(drone_pitch + int(y.strip())))
            loc = calc_pos(loc=drone_loc, distance=abs_distance, bearing=(drone_yaw + int(x.strip())))

            print(f"Hedeflenen konum dronedan {calc_distance(loc1=loc, loc2=drone_loc)} metre uzak\nisaretlenen hedef dronedan {abs_distance} metre uzak")
            print("Hedeflenen konum: ", loc)
            break
        
        start_time = time.time()
        while time.time() - start_time <= 0.5:
            time.sleep(0.05)
    
    if loc is not None:
        vehicle.go_to(loc=loc, alt=ALT, drone_id=DRONE_ID)

        print("Hedeflenen konuma gidiliyor")
        while not stop_event.is_set() and not vehicle.on_location(loc=loc, drone_id=DRONE_ID):
            time.sleep(0.5)

        print("Hedeflenen konuma vardı 8sn bekleniyor")
        time.sleep(8)

        print("Kalkis konumuna donuyor")
        failsafe(vehicle=vehicle)
        

except Exception as e:
    failsafe(vehicle=vehicle)
    print(e)
except KeyboardInterrupt:
    failsafe(vehicle=vehicle)
    print("CTRL+C ile cikildi")
    if not stop_event.is_set():
        stop_event.set()
finally:
    if not stop_event.is_set():
        stop_event.set()
    vehicle.close()