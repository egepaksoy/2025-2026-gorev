import time, threading
from utils import TCP_HANDLER


TCP_PORT = 5005     # Dinlenecek port

stop_event = threading.Event()

# Ek sistem kontrolculeri
tcp_handler = TCP_HANDLER(port=TCP_PORT, stop_event=stop_event)
tcp_handler.connect()
print("Connected")

while not stop_event.is_set():
    data = tcp_handler.get_data()
    if data is not None:
        print(data)
    time.sleep(0.05)