# Raspberry pi kamera ve gimbal kontrol kodu
import socket
import serial
import time

import smbus

import io
import struct
from picamera2 import Picamera2
import cv2
from math import ceil

import threading

# --- Yapılandırma ---
# TCP Ayarları
TCP_IP = '0.0.0.0'  # Tüm arayüzlerden dinle
TCP_PORT = 5005     # Dinlenecek port
BUFFER_SIZE = 1024  # Her seferinde okunacak maksimum bayt

# Seri Port (Arduino) Ayarları
# Raspberry Pi'de Arduino genellikle /dev/ttyACM0 veya /dev/ttyUSB0 olarak görünür.
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 9600    # Arduino tarafındaki Serial.begin(9600) ile aynı olmalı

stop_event = threading.Event()

data_sended = False

def start_sender(stop_event: threading.Event, host='0.0.0.0', port=9999):
    # Sunucu (Alıcı) soketini oluştur
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"Gönderici {port} portunda bekleniyor (Picamera2 aktif)...")

    try:
        client_socket, addr = server_socket.accept()
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Nagle algoritmasını devre dışı bırak
        print(f"Alıcı bağlandı: {addr}")
        
        picam2 = Picamera2()
        # Kamera ayarları
        config = picam2.create_video_configuration(main={"size": (640, 480)})
        picam2.configure(config)
        picam2.start()
        
        # Kameranın ısınması için kısa bir bekleme
        time.sleep(2)

        stream = io.BytesIO()

        # Sürekli olarak JPEG formatında yakala ve gönder
        while not stop_event.is_set():
            stream.seek(0)
            stream.truncate()
            
            # Görüntüyü stream'e JPEG olarak yakala
            picam2.capture_file(stream, format='jpeg')
            
            # Verinin boyutunu al
            image_len = stream.tell()
            if image_len > 0:
                # Önce boyutu (unsigned long), sonra veriyi gönder
                client_socket.sendall(struct.pack(">L", image_len))
                
                stream.seek(0)
                client_socket.sendall(stream.read())
            
    except Exception as e:
        print(f"Kamera/Gönderici Hatası: {e}")
    finally:
        if 'picam2' in locals():
            picam2.stop()
        if 'client_socket' in locals():
            client_socket.close()
        server_socket.close()
        print("Kamera ve bağlantı kapatıldı.")

def get_distance(repeat=5, LIDAR_ADDRESS = 0x62):
    """ 
    LIDAR Lite v3'ten mesafe okur, birkaç ölçüm alarak ortalama hesaplar.
    repeat: Ortalama alınacak ölçüm sayısı (Gürültüyü azaltır).
    """

    bus = smbus.SMBus(1)  # Raspberry Pi'de I2C-1 hattı kullanılıyor
    distances = []
    
    for _ in range(repeat):
        try:
            # LIDAR'a ölçüm yapmasını söyle
            bus.write_byte_data(LIDAR_ADDRESS, 0x00, 0x04)
            time.sleep(0.02)  # Ölçüm süresi

            # 16-bit mesafe verisini oku
            high_byte = bus.read_byte_data(LIDAR_ADDRESS, 0x0f)
            low_byte = bus.read_byte_data(LIDAR_ADDRESS, 0x10)
            distance_cm = (high_byte << 8) + low_byte  # Mesafeyi cm olarak hesapla

            if 100 < distance_cm < 4000:  # LIDAR'ın ölçebileceği mesafe aralığı
                distances.append(distance_cm)
            else:
                print("Geçersiz ölçüm alındı, tekrar deneniyor...")
            
        except OSError:
            print("I2C bağlantı hatası! LIDAR bağlı mı?")
            return None  # Bağlantı hatası olursa None döndür

        time.sleep(0.001)  # Sensörün stabilize olması için bekleme süresi
    
    if not distances:
        return None  # Geçerli ölçüm alınamadıysa None döndür

    avg_distance_cm = sum(distances) / len(distances)  # Ölçümleri ortalama alarak hassasiyeti artır
    avg_distance_m = avg_distance_cm / 100  # Metreye çevir

    return round(avg_distance_m, 3)  # Ölçümü metre cinsinden 3 ondalık basamakla döndür


def main(stop_event: threading.Event):
    threading.Thread(target=start_sender, daemon=True, args=(stop_event, )).start()
    
    # Seri port bağlantısını kur
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ser.write("0|0".encode("utf-8"))
        print(f"Seri port açıldı: {SERIAL_PORT} @ {BAUD_RATE}")
        time.sleep(2)  # Arduino'nun resetlenmesi için bekle
    except Exception as e:
        print(f"Seri port açılamadı: {e}")
        # Eğer /dev/ttyACM0 yoksa /dev/ttyUSB0 dene (alternatif)
        try:
            ser = serial.Serial('/dev/ttyACM0', BAUD_RATE, timeout=1)
            ser.write("0|0")
            print(f"Seri port açıldı: /dev/ttyACM0 @ {BAUD_RATE}")
            time.sleep(2)
        except Exception as e2:
            print(f"Alternatif seri port da açılamadı: {e2}")
            ser = None

    # TCP Sunucusunu başlat
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Portu hemen tekrar kullanılabilir yap
    server_socket.bind((TCP_IP, TCP_PORT))
    server_socket.listen(1)

    print(f"TCP Sunucusu başlatıldı. {TCP_IP}:{TCP_PORT} portu dinleniyor...")

    try:
        while not stop_event.is_set():
            print("Yeni bir bağlantı bekleniyor...")
            try:
                server_socket.settimeout(1.0) # stop_event kontrolü için periyodik timeout
                conn, addr = server_socket.accept()
            except socket.timeout:
                continue

            print(f"Bağlantı kabul edildi: {addr}")

            with conn:
                while not stop_event.is_set():
                    ser_value = None
                    if ser.in_waiting > 0:
                        ser_value = str(ser.readline().decode("utf-8", errors='ignore')).strip()

                    data_bytes = conn.recv(BUFFER_SIZE)
                    if not data_bytes:
                        print("İstemci bağlantıyı kapattı.")
                        break

                    # Alınan veriyi string'e dönüştür (utf-8)
                    try:
                        data_str = data_bytes.decode('utf-8').strip()
                        #print(f"Alınan veri (TCP String): {data_str}")

                        if "fizz" in data_str or "buzz" in data_str:
                            if "fizz" in data_str:
                                conn.sendall("buzz".encode())
                            else:
                                conn.sendall("fizz".encode())

                        else:
                            # YKİ'ye veri gonderme
                            if "get" in data_str and not data_sended:
                                ser.write(("0|0" + '\n').encode('utf-8'))

                                if not ser_value or "|" not in ser_value:
                                    print("Uyarı: Arduino'dan geçerli cevap alınamadı. Varsayılan değer kullanılıyor.")
                                    ser_value = "0|0"
                            
                                distance = get_distance()
                                #print(f"ser value: {ser_value}")
                                #print(f"distance: {distance}")
                                data = f"{distance}|{ser_value.split('|')[0]}|{ser_value.split('|')[1]}"
                                conn.sendall(data.encode())
                                print(f"Gönderilen veri: {data}")
                                data_sended = True

                            elif "get" not in data_str and "|" in data_str:
                                data_sended = False
                                # String veriyi Arduino'ya gönder
                                if ser is not None:
                                    ser.write((data_str + '\n').encode('utf-8'))
                                    #print(f"'{data_str}' verisi Arduino'ya iletildi.")

                    except UnicodeDecodeError:
                        print("Gelen veri utf-8 formatında çözülemedi, ham veri gönderiliyor.")
                        if ser is not None:
                            ser.write(data_bytes)
                    
                    time.sleep(0.05)
                
    except KeyboardInterrupt:
        if not stop_event.is_set():
            stop_event.set()
        print("\nKullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Bir hata oluştu: {e}")
    finally:
        server_socket.close()
        if ser is not None:
            ser.close()
        print("Bağlantılar kapatıldı.")

if __name__ == "__main__":
    main(stop_event=stop_event)
