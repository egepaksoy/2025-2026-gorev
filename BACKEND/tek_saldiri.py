from saldiri_handler import Saldiri
from pymavlink_custom.pymavlink_custom import Vehicle, failsafe
import json
import threading


CONFIG_FILE = "./drone_conf.json"
with open(CONFIG_FILE, "r") as f:
    conf = json.load(f)

stop_event = threading.Event()
vehicle = Vehicle(address="udp:172.22.160.1:14550")
saldiri = Saldiri(vehicle=vehicle, drone_conf=conf["saldiri"], stop_event=stop_event)

hedefler = {"red": (-35.36318322, 149.16513032), "blue": (-35.36318322, 149.16513032)}

try:
    saldiri.baglantilari_kur()
    saldiri.gorevi_baslat(hedef_siniflari=hedefler)

except KeyboardInterrupt:
    failsafe(vehicle=vehicle)
except Exception as e:
    failsafe(vehicle=vehicle)
finally:
    if not stop_event.is_set():
        stop_event.set()
    saldiri.kapat()