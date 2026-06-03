# Lidar kontrol kodu
import threading
import time
import json

from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler
from libs.joystick_handler import Joystick_Handler
from libs.utils import joystick_value_split


stop_event = threading.Event()
RASP_IP = "192.168.31.108"
UDP_PORT = 9999
TCP_PORT = 5005

CARPAN = 2

img_handler = Handler(stop_event=stop_event)
joystick_handler = Joystick_Handler(stop_event=stop_event, port="COM15")

# Goruntu isleme threadi
threading.Thread(target=img_handler.udp_camera, args=(RASP_IP, UDP_PORT), daemon=True).start()
# Arduino veri okuma threadi
threading.Thread(target=joystick_handler.value_reader, daemon=True).start()

# Gimbal baglantisi
client = TCPClient(host=RASP_IP, port=TCP_PORT)
client.connect()

try:
    while not stop_event.is_set():
        raw_value = joystick_handler.get_value()
        joystick_value = joystick_value_split(raw_value)
        print("raw_value: ", raw_value)
        print("splitted_value: ", joystick_value)
        if joystick_value is None:
            continue

        if joystick_value["btn1"] == 1:
            client.send_data("get")
            print(client.get_data())
        else:
            client.send_data(f"{joystick_value['x'] * CARPAN}|{joystick_value['y']*-1 * CARPAN}")

        time.sleep(0.1)

except KeyboardInterrupt:
    print("CTRL+C ile cikildi")

finally:
    stop_event.set()