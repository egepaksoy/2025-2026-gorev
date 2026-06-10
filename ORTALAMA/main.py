import threading, time

from pymavlink_custom.pymavlink_custom import Vehicle, failsafe

from saldiri_handler import Saldiri

import json

#? Test edilcek
stop_event = threading.Event()

drone_conf = json.load(open("./drone_conf.json", "r"))
VEHICLE_ADDR = drone_conf["address"]

hedefler = {"blue": (-35.36306108, 149.16528559)}

def main(stop_event: threading.Event=threading.Event()):
    try:
        vehicle = Vehicle(address=VEHICLE_ADDR, stop_event=stop_event)
        saldiri = Saldiri(vehicle=vehicle, drone_conf=drone_conf["saldiri"], hedef_siniflari=hedefler, model_path="./models/kullanilcak.pt", stop_event=stop_event)

        saldiri.baglantilari_kur()

        print("5 SN Bekleniyor")
        time.sleep(5)
        
        print("Ucus gorevi baslatiliyor")
        saldiri.gorevi_baslat()

        while not stop_event.is_set():
            time.sleep(1)

    except Exception as e:
        print(e)
        failsafe(vehicle=vehicle)
    except KeyboardInterrupt:
        print("CTRL+C ile cikildi")
        failsafe(vehicle=vehicle)
    finally:
        print("Stop event set edildi")
        if stop_event.is_set():
            stop_event.set()


if __name__ == "__main__":
    main(stop_event=stop_event)