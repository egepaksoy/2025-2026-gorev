from pymavlink_custom.pymavlink_custom import Vehicle
import threading, time

stop_event = threading.Event()

vehicle = Vehicle(address="com10", stop_event=stop_event)

try:
    while True:
        input("yuk takın")
        vehicle.set_servo(channel=13, pwm=1500, drone_id=1)
        vehicle.set_servo(channel=14, pwm=1000, drone_id=1)
        input("yuk birakilcak")
        vehicle.set_servo(channel=13, pwm=1000, drone_id=1)
        vehicle.set_servo(channel=14, pwm=1600, drone_id=1)

except KeyboardInterrupt:
    print("CTRL+C")

finally:
    if not stop_event.is_set():
        stop_event.set()
        