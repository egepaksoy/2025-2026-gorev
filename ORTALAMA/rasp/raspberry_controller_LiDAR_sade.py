# Raspberry pi kamera ve gimbal kontrol kodu
import time, threading

from utils import TCP_HANDLER, VIDEO_HANDLER, AURDUINO_HANDLER, get_distance

# --- Yapılandırma ---
# TCP AYARLARI
TCP_PORT = 5005     # Dinlenecek port

# KAMERA AYARLARI
UDP_PORT = 9999

# AURDUINO AYARLARI
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 9600    # Arduino tarafındaki Serial.begin(9600) ile aynı olmalı

# Kullanılan degiskenler
stop_event = threading.Event()
data_sended = False

# Ek sistem kontrolculeri
tcp_handler = TCP_HANDLER(port=TCP_PORT, stop_event=stop_event)
video_handler = VIDEO_HANDLER(port=UDP_PORT, stop_event=stop_event)
aurduino_handler = AURDUINO_HANDLER(serial_port=SERIAL_PORT, baud_rate=BAUD_RATE, stop_event=stop_event)

connectors = [tcp_handler, video_handler, aurduino_handler]
for connector in connectors:
    print(f"{connector}")
    threading.Thread(target=connector.connect, daemon=True).start()

print("Tum baglantilarin tamamlanmasi bekleniyor")
start_time = time.time()
while not stop_event.is_set():
    if tcp_handler.connected and aurduino_handler.connected and video_handler.connected :
        break
    
    if time.time() - start_time >= 2:
        # \r ile satır başına dönüyoruz, \033[K ile o satırı temizliyoruz
        print(
            f"\r\033[K[DURUM]>> TCP: {tcp_handler.connected} | Video: {video_handler.connected} | Arduino: {aurduino_handler.connected}", 
            end="", 
            flush=True
        )
        start_time = time.time()
        
    time.sleep(0.05)

# Döngü bittiğinde alt satıra geçmek ve temiz bir onay mesajı basmak için:
print("\n[OK]>> Tum baglantilar tamamlandi")

def main(stop_event: threading.Event):
    try:
        while not stop_event.is_set() and tcp_handler.connected and video_handler.connected:
            received_data = tcp_handler.get_data()

            if received_data is None:
                time.sleep(0.05)
                continue

            if "fizz" in received_data:
                tcp_handler.send_data("buzz")
            elif "buzz" in received_data:
                tcp_handler.send_data("fizz")
            
            else:
                if "get" in received_data and not data_sended:
                    aurduino_handler.write_value("0|0")

                    ser_value = aurduino_handler.get_value()

                    if ser_value is None:
                        print("!!Aurduinodan gecerli veri alinamadi!!")
                        continue

                    distance = get_distance()
                    data = f"{distance}|{ser_value.split('|')[0]}|{ser_value.split('|')[1]}"
                    tcp_handler.send_data(data.encode())
                    print(f"Gönderilen veri: {data}")
                    data_sended = True

                elif "|" in received_data:
                    data_sended = False
                    # String veriyi Arduino'ya gönder
                    if aurduino_handler.connected:
                        aurduino_handler.write_value(received_data)
                        #print(f"'{data_str}' verisi Arduino'ya iletildi.")

            time.sleep(0.05)
                
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")

    except Exception as e:
        print(f"Bir hata oluştu: {e.args}")
    
    finally:
        if not stop_event.is_set():
            stop_event.set()
        tcp_handler.close()
        video_handler.close()
        aurduino_handler.close()

        print("Bağlantılar kapatıldı.")

if __name__ == "__main__":
    main(stop_event=stop_event)
