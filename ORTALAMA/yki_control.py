from libs.joystick_handler import Joystick_Handler
import threading
import time


stop_event = threading.Event()

try:
    handler = Joystick_Handler(stop_event=stop_event, port="COM15")

    #threading.Thread(target=handler.value_reader, daemon=True).start()
    while True:
        #with handler.ser_lock:
        #    print(handler.ser_value)
        print(handler.read_line())
        time.sleep(0.1)

finally:
    stop_event.set()