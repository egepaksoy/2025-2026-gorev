from pymavlink_custom.pymavlink_custom import Vehicle, failsafe
import threading
import time


stop_event = threading.Event()
vehicle = Vehicle(address="udp:172.22.160.1:14550", stop_event=stop_event)

while True:
    i = input("Failsafe icin f yazin cikmak icin x: ")
    if i == "f":
        failsafe(vehicle=vehicle)
    if i == "x":
        exit()