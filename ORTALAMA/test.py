from libs.lidar_controller import Lidar_Handler
from libs.joystick_handler import Joystick_Handler
from libs.tcp_client import TCPClient

import threading, time

stop_event = threading.Event()
joystick_handler = Joystick_Handler(stop_event=stop_event, port="com15")
tcp_client = TCPClient(host="192.168.31.108", port=5005)

lidar_handler = Lidar_Handler(stop_event=stop_event, joystick_handler=joystick_handler, tcp_client=tcp_client)

try:
    while not stop_event.is_set():
        val = lidar_handler.get_value()
        if val is not None:
            print(val)
        time.sleep(0.5)

finally:
    stop_event.set()