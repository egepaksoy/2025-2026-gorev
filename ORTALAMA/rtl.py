from pymavlink_custom.pymavlink_custom import Vehicle, failsafe
import threading
import time


stop_event = threading.Event()
vehicle = Vehicle(address="com9", stop_event=stop_event)

for d_id in vehicle.get_all_drone_ids():
    vehicle.set_mode(mode="LAND", drone_id=d_id)
    time.sleep(1)