import time
import sys
from pymavlink_custom.pymavlink_custom import Vehicle, calc_distance

vehicle = Vehicle(address="com9")

start_time = time.time()

try:
    while True:
        if time.time() - start_time >= 2:
            pos_1 = vehicle.get_pos(drone_id=1)
            pos_2 = vehicle.get_pos(drone_id=2)

            alt_1 = pos_1[2]
            alt_2 = pos_2[2]

            yaw_1 = vehicle.get_yaw(drone_id=1)
            yaw_2 = vehicle.get_yaw(drone_id=2)

            print("="*50)
            print(f"1. drone konumu: {pos_1[:2]}")
            print(f"2. drone konumu: {pos_2[:2]}")
            print(f"drone konumları arasındaki fark: {calc_distance(pos_1[:2], pos_2[:2])}")
            print("-"*50)
            print(f"1. drone yuksekligi: {alt_1}")
            print(f"2. drone yuksekligi: {alt_2}")
            print(f"drone yuksekligi arasındaki fark: {abs(alt_1- alt_2)}")
            print("-"*50)
            print(f"1. drone yaw: {yaw_1}")
            print(f"2. drone yaw: {yaw_2}")
            print(f"drone yaw arasındaki fark: {abs(yaw_1 - yaw_2)}")
            print("="*50)
            start_time = time.time()
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Exiting...")

except Exception as e:
    print(e)

finally:
    vehicle.vehicle.close()
