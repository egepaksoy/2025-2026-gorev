import serial.tools.list_ports
import sys
import threading
import time

class Joystick_Handler:
    def __init__(self, stop_event: threading.Event=None, port=None):
        self.port = port

        self.ser_value = None
        self.ser_lock = threading.Lock()

        if stop_event is None:
            self.stop_event = threading.Event()
        else:
            self.stop_event = stop_event
        
        self.connected = False
        self.ser = self.connect_serial()

        # Arduino veri okuma threadi
        threading.Thread(target=self.value_reader, daemon=True).start()

        self.tested = self.test()
    
    def connect_serial(self):
        """Seri porta bağlanır."""
        if not self.connected:
            seri_portlar = serial.tools.list_ports.comports()
            if self.port == None:
                seri_port = ""
                print("Seri portlar listelendi.")
                for port in seri_portlar:
                    if "ch340" in port.description.lower():
                        seri_port = port.device
                        break
            else:
                seri_port = self.port

            if seri_port == "":
                print("CH340 çevirici bulunamadı!")
                sys.exit(1)
            
            try:
                ser = serial.Serial(seri_port, 115200)  # Arduino'nun bağlı olduğu portu ve baud rate'i belirle
                print("Bağlantı sağlandı:", ser.name)
                self.connected = True
                return ser
            except Exception as e:
                print(f"Arduino baglanti hatasi: {e}")
                self.connected = False
                return None
    
    def read_line(self):
        if self.ser.in_waiting > 0:
            return str(self.ser.readline().decode("utf-8", errors='ignore')).strip()
        return None


    def value_reader(self):
        """Seri porttan veri okur."""
        while not self.stop_event.is_set():
            ser_value = self.read_line()
            if ser_value is None or ser_value == "":
                continue
            with self.ser_lock:
                self.ser_value = ser_value
            
            time.sleep(0.05)

    def get_value(self):
        """Veriyi dondurur."""
        with self.ser_lock:
            return self.ser_value
        return None
    
    def test(self):
        try:
            while self.get_value() is None:
                time.sleep(0.05)
            
            print("[TEST]>> Joystick testi basarili")
            return True
        except Exception as e:
            print(f"[TEST]>> Joystick testi basarisiz: {e}")
            return False
    
    def close(self):
        self.ser.close()