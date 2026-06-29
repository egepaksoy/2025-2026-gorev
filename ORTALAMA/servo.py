from pymavlink_custom.pymavlink_custom import Vehicle
import threading, time

stop_event = threading.Event()

vehicle = Vehicle(address="com12", stop_event=stop_event)

try:
    while True:
        vehicle.set_servo(channel=13, pwm=1800, drone_id=2)
        vehicle.set_servo(channel=14, pwm=1100, drone_id=2)
        input("Yuk takın")
        vehicle.set_servo(channel=13, pwm=1400, drone_id=2)
        vehicle.set_servo(channel=14, pwm=1600, drone_id=2)
        input("yuk birakildcak")

except KeyboardInterrupt:
    print("CTRL+C")

finally:
    if not stop_event.is_set():
        stop_event.set()