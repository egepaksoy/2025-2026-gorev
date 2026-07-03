from pymavlink_custom.pymavlink_custom import Vehicle
import threading, time, json

stop_event = threading.Event()

drone_conf = json.load(open("../BACKEND/drone_conf.json", "r"))
vehicle = Vehicle(address="com9", stop_event=stop_event)

try:
    while True:
        input("yuk takın")
        vehicle.set_servo(channel=drone_conf["saldiri"]["yuk1"]["channel"], pwm=drone_conf["saldiri"]["yuk1"]["kapali"], drone_id=1)
        vehicle.set_servo(channel=drone_conf["saldiri"]["yuk2"]["channel"], pwm=drone_conf["saldiri"]["yuk2"]["kapali"], drone_id=1)
        input("yuk birakilcak")
        vehicle.set_servo(channel=drone_conf["saldiri"]["yuk1"]["channel"], pwm=drone_conf["saldiri"]["yuk1"]["acik"], drone_id=1)
        vehicle.set_servo(channel=drone_conf["saldiri"]["yuk2"]["channel"], pwm=drone_conf["saldiri"]["yuk2"]["acik"], drone_id=1)

except KeyboardInterrupt:
    print("CTRL+C")

finally:
    if not stop_event.is_set():
        stop_event.set()
        