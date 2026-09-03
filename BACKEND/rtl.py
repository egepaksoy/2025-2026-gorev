from pymavlink_custom.pymavlink_custom import Vehicle
import time

vehicle = Vehicle("com9")
for d_id in vehicle.get_all_drone_ids():
    vehicle.set_mode(mode="RTL", drone_id=d_id)
    time.sleep(1)