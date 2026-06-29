import time
import sys
from pymavlink_custom.pymavlink_custom import Vehicle

vehicle = Vehicle(address="com9")

start_time = time.time()

try:
    while True:
        if time.time() - start_time >= 2:
            for i in vehicle.get_all_drone_ids():
                print(f"{i}: {vehicle.get_mode(drone_id=i)}")
                print(f"{i}: {vehicle.get_pos(drone_id=i)}")
            start_time = time.time()
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Exiting...")

except Exception as e:
    print(e)

finally:
    vehicle.vehicle.close()
