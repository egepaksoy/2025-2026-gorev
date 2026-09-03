import threading
import time

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe

stop_event = threading.Event()

vehicle = Vehicle(address="com9", stop_event=stop_event)
# vehicle = Vehicle(address="com9", stop_event=stop_event, log_messages=True)
DRONE_ID = 2
ALT = 5
    
try:
    input("Enter")
    #? Mode GUIDED beklemesi
    vehicle.set_mode(mode="GUIDED", drone_id=DRONE_ID)
    print(f"{DRONE_ID}>> Mode GUIDED yapildi TAKEOFF aliniyor")

    #? Takeoff
    vehicle.arm_disarm(arm=True, drone_id=DRONE_ID)
    takeoff_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
    print("Kalkis oncesi drone yaw'i: ", takeoff_yaw)
    vehicle.multiple_takeoff(alt=ALT, drone_id=DRONE_ID)
    while not stop_event.is_set():
        if abs(vehicle.get_pos(drone_id=DRONE_ID)[2] - ALT) <= 0.1:
            break
        time.sleep(0.05)

    yaw_angle = vehicle.get_yaw(drone_id=DRONE_ID)
    print(f"yaw acisi: {yaw_angle}")

    if True:
        print(f"aradaki fark: ", abs(takeoff_yaw - yaw_angle), " donuyor")

        vehicle.set_yaw(turn_angle=takeoff_yaw, drone_id=DRONE_ID, default_speed=14, relative=False)
        while not stop_event.is_set() and abs(vehicle.get_yaw(drone_id=DRONE_ID) - (takeoff_yaw) % 360) > 9:
            time.sleep(0.05)

        print(vehicle.get_yaw(drone_id=DRONE_ID), " yonune dondu")

    print("5 sn bekliyor")
    time.sleep(5)

    vehicle.set_mode(mode="LAND", drone_id=DRONE_ID)
    land_yaw = vehicle.get_yaw(drone_id=DRONE_ID)
    print(f"inis yaw acisi: {land_yaw}")
    time.sleep(2)

    print("\n")
    print("="*50)
    print(f"Kalkis yaw: {takeoff_yaw}")
    print(f"Ucus yaw: {yaw_angle}")
    print(f"inis yaw: {land_yaw}")
    print(f"kalkis_ucus: {abs(takeoff_yaw-yaw_angle)}")
    print(f"kalkis_inis: {abs(takeoff_yaw-land_yaw)}")
    print(f"ucus_inis: {abs(yaw_angle-land_yaw)}")
    print("="*50)


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