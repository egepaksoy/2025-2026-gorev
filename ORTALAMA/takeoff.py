import threading
import time

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe

stop_event = threading.Event()

#vehicle = Vehicle(address="com6", stop_event=stop_event)
vehicle = Vehicle(address="udp:172.22.160.1:14550", stop_event=stop_event, log_messages=True)
DRONE_ID = 1
ALT = 5
    
try:
    input("Enter")
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
    time.sleep(5)

    failsafe(vehicle)
    

except KeyboardInterrupt:
    print("Koddan cikildi")
    failsafe(vehicle)

except Exception as e:
    print(e)
    failsafe(vehicle)

finally:
    while vehicle.is_armed(drone_id=DRONE_ID):
        time.sleep(0.5)
    if not stop_event.is_set():
        stop_event.set()
    vehicle.close()