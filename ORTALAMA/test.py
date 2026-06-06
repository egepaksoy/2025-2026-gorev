from libs.tcp_client import TCPClient
from libs.joystick_handler import Joystick_Handler
from libs.lidar_controller import Lidar_Handler

import threading, time

stop_event = threading.Event()

RASP_IP = "192.168.0.120"
TCP_PORT = 5005
UDP_PORT = 9999
JOYSTICK_COM_PORT = "COM15"

joystick_handler = Joystick_Handler(stop_event=stop_event, port=JOYSTICK_COM_PORT)

# TCP Baglantı ve baglantı testi
tcp_client = TCPClient(host=RASP_IP, port=TCP_PORT)

# Lidar kontrolcusu
lidar_handler = Lidar_Handler(stop_event=stop_event, joystick_handler=joystick_handler, tcp_client=tcp_client)

while not stop_event.is_set() and not tcp_client.connected:
    time.sleep(0.5)
print("Baglanti saglandi")

try:
    while not stop_event.is_set():
        time.sleep(0.05)

finally:
    stop_event.set()