# Raspberry pi kamera ve gimbal kontrol kodu
import time, threading

from utils import TCP_HANDLER, VIDEO_HANDLER, ARDUINO_HANDLER, get_distance


# --- Yapılandırma ---
# TCP Ayarları
TCP_IP = '0.0.0.0'  # Tüm arayüzlerden dinle
TCP_PORT = 5005     # Dinlenecek port

# KAMERA AYARLARI
UDP_PORT = 9999

# AURDUINO AYARLARI
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 9600    # Arduino tarafındaki Serial.begin(9600) ile aynı olmalı

stop_event = threading.Event()

tcp_handler = TCP_HANDLER(port=TCP_PORT, stop_event=stop_event)
video_handler = VIDEO_HANDLER(port=UDP_PORT, stop_event=stop_event)
arduino_handler = ARDUINO_HANDLER(serial_port=SERIAL_PORT, baud_rate=BAUD_RATE, stop_event=stop_event)

connectors = [tcp_handler, video_handler, arduino_handler]
for connector in connectors:
    print(f"{connector}")
    threading.Thread(target=connector.connect, daemon=True).start()

print("Tum baglantilarin tamamlanmasi bekleniyor")
time.sleep(1)
start_time = time.time()
while not stop_event.is_set():
    if tcp_handler.connected and arduino_handler.connected and video_handler.connected :
        break
    
    if time.time() - start_time >= 2:
        # \r ile satır başına dönüyoruz, \033[K ile o satırı temizliyoruz
        print(
            f"\r\033[K[DURUM]>> TCP: {tcp_handler.connected} | Video: {video_handler.connected} | Arduino: {arduino_handler.connected}", 
            end="", 
            flush=True
        )
        start_time = time.time()
        
    time.sleep(0.05)

# Döngü bittiğinde alt satıra geçmek ve temiz bir onay mesajı basmak için:
print("\n[OK]>> Tum baglantilar tamamlandi")

def main(stop_event: threading.Event):
    try:
        while not stop_event.is_set():
            received_data = tcp_handler.get_data()
            if received_data is None:
                time.sleep(0.05)
                continue
            print(received_data)

            # Alınan veriyi string'e dönüştür (utf-8)
            arduino_handler.write_value(received_data)
            print(f"'{received_data}' verisi Arduino'ya iletildi.")
        
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Bir hata oluştu: {e}")
    finally:
        if not stop_event.is_set():
            stop_event.set()
        tcp_handler.close()
        video_handler.close()
        arduino_handler.close()

        print("Bağlantılar kapatıldı.")

if __name__ == "__main__":
    main(stop_event=stop_event)
