# from saldiri_handler import Saldiri
from saldiri_handler_ege import Saldiri
from pymavlink_custom.pymavlink_custom import Vehicle, failsafe
import json
import threading


CONFIG_FILE = "./drone_conf.json"
with open(CONFIG_FILE, "r") as f:
    conf = json.load(f)

stop_event = threading.Event()
vehicle = Vehicle(address="com9")
saldiri = Saldiri(vehicle=vehicle, drone_conf=conf["saldiri"], stop_event=stop_event)

hedefler = {'blue':[40.7120645, 30.0246167] , 'red': [40.7120664, 30.0245069]}
try:    
    saldiri.baglantilari_kur()
    saldiri.image_handler.showing_image = True

    input("Entera basin")
    saldiri.gorevi_baslat(hedef_siniflari=hedefler)

except KeyboardInterrupt:
    failsafe(vehicle=vehicle)
except Exception as e:
    failsafe(vehicle=vehicle)
finally:
    if not stop_event.is_set():
        stop_event.set()