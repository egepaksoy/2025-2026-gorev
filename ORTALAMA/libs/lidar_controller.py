# Lidar kontrol kodu
#? Tek basına test et mukemmel hale getir
import threading
import time
import json

from libs.tcp_client import TCPClient
from libs.image_proccesser import Handler
from libs.joystick_handler import Joystick_Handler
from libs.utils import joystick_value_split


class Lidar_Handler():
    def __init__(self, stop_event: threading.Event, joystick_handler: Joystick_Handler, tcp_client: TCPClient, carpan: int=2):
        self.stop_event = stop_event

        self.CARPAN = carpan

        self.joystick_handler = joystick_handler
        self.tcp_client = tcp_client

        self.rasp_value = None
        self.value_lock = threading.Lock()

        threading.Thread(target=self.controller, daemon=True).start()

    def controller(self):
        print("[LIDAR_CONTROLLER]>> Started")
        try:
            while not self.stop_event.is_set():
                raw_value = self.joystick_handler.get_value()
                joystick_value = joystick_value_split(raw_value)
                if joystick_value is None:
                    continue

                if joystick_value["btn1"] == 1:
                    self.tcp_client.send_data("get")
                    
                    recieved_value = self.tcp_client.get_data()
                    if recieved_value is not None:
                        with self.value_lock:
                            self.rasp_value = recieved_value
                else:
                    # TODO: buradaki carpan nesneye yaklastikca azaltilabilir
                    self.tcp_client.send_data(f"{joystick_value['x'] * self.CARPAN}|{joystick_value['y']*-1 * self.CARPAN}")

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("CTRL+C ile cikildi")
    
    def get_value(self):
        recieved_value = None
        with self.value_lock:
            recieved_value = self.rasp_value
            self.rasp_value = None
        return recieved_value