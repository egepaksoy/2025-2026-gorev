import serial.tools.list_ports
import sys
import threading
import time

class Joystick_Handler:
    def __init__(self, stop_event: threading.Event=None, port=None, baud_rate: int=115200):
        self.port = port
        self.baud_rate = baud_rate

        self.ser_value = None
        self.ser_lock = threading.Lock()

        if stop_event is None:
            self.stop_event = threading.Event()
        else:
            self.stop_event = stop_event
        
        self.connected = False
        self.ser = self.connect_serial()

        if self.connected:
            # Bağlantı ilk açıldığında buffer'da kalan eski/yarım verileri temizle
            self.ser.reset_input_buffer()
            
            # Arduino veri okuma threadi
            threading.Thread(target=self.value_reader, daemon=True).start()
            self.tested = self.test()
        else:
            self.tested = False
    
    def connect_serial(self):
        """Seri porta bağlanır."""
        if not self.connected:
            seri_portlar = serial.tools.list_ports.comports()
            if self.port is None:
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
                # timeout=1 ekleyerek readline()'ın sonsuza kadar kilitlenmesini önlüyoruz
                ser = serial.Serial(seri_port, self.baud_rate, timeout=1)  
                print("Bağlantı sağlandı:", ser.name)
                self.connected = True
                return ser
            except Exception as e:
                print(f"Arduino baglanti hatasi: {e}")
                self.connected = False
                return None
    
    def read_line(self):
        """Seri porttan ham satırı okur (Kilit mekanizması dışında olmalıdır)."""
        try:
            if self.ser and self.ser.in_waiting > 0:
                raw_data = self.ser.readline()
                return raw_data.decode("utf-8", errors='ignore').strip()
        except Exception as e:
            print(f"Okuma hatası: {e}")
        return None

    def is_valid_string(self, data_str):
        """Gelen verinin tam satır olup olmadığını doğrular."""
        # Satırın tam olması için hem başında 'X:' hem de sonunda 'Buton_2:' formatı aranır
        if data_str and "X:" in data_str and "Buton_2:" in data_str:
            return True
        return False

    def value_reader(self):
        """Seri porttan veri okur ve doğrular."""
        while not self.stop_event.is_set():
            # Seri okuma işlemini Lock (kilit) DIŞINDA yapıyoruz. 
            # Böylece ana thread get_value() çağırdığında bu thread'i kilitlemez.
            ser_value = self.read_line()
            
            if ser_value:
                # Verinin yarım mı tam mı olduğunu kontrol et
                if self.is_valid_string(ser_value):
                    with self.ser_lock:
                        self.ser_value = ser_value
                    # İsteğe bağlı: print(ser_value) -> Çok hızlı akıyorsa terminali yorabilir
                else:
                    # Yarım gelen satırları debug için görebilirsin, sonra silebilirsin
                    print(f"[YARIM SATIR ELENDİ]>> {ser_value}")
                    self.ser.reset_input_buffer()
                    pass
            
            time.sleep(0.01) # Daha hassas okuma için süreyi biraz düşürdük

    def get_value(self):
        """Veriyi döndürür."""
        with self.ser_lock:
            return self.ser_value
    
    def test(self):
        try:
            print("[TEST]>> Joystick verisi bekleniyor...")
            start_time = time.time()
            while self.get_value() is None:
                time.sleep(0.05)
                if time.time() - start_time > 5:
                    raise TimeoutError("5 saniye boyunca geçerli veri alınamadı.")
            
            print("[TEST]>> Joystick testi basarili. Geçerli veri akışı var.")
            return True
        except Exception as e:
            print(f"[TEST]>> Joystick testi basarisiz: {e}")
            return False
    
    def close(self):
        if self.ser:
            self.ser.close()
        self.connected = False