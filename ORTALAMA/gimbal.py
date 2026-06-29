from gozlemci_handler import Gozlemci
from saldiri_handler import Saldiri
from pymavlink_custom.pymavlink_custom import Vehicle
import threading, time, json

with open("./drone_conf.json", "r") as conf:
    conf_file = json.load(conf)

hedef_siniflari = {"red": [0,0]}
stop_event = threading.Event()
vehicle = Vehicle(address=conf_file["address"], stop_event=stop_event, on_flight=False)

gozlemci = Gozlemci(vehicle=vehicle, drone_conf=conf_file["gozlemci"], stop_event=stop_event)
#saldiri = Saldiri(vehicle=vehicle, drone_conf=conf_file["saldiri"], hedef_siniflari=hedef_siniflari, model_path="./models/model.pt", stop_event=stop_event)

gozlemci.baglantilari_kur()
#saldiri.baglantilari_kur()


threading.Thread(target=gozlemci.gorevi_baslat, daemon=True).start()
#threading.Thread(target=saldiri.gorevi_baslat, args=(hedef_siniflari, ), daemon=True).start()


try:
    while not stop_event.is_set():
        time.sleep(0.5)

except KeyboardInterrupt:
    print("CTRL+C ile cikildi")

finally:
    if not stop_event.is_set():
        stop_event.set()