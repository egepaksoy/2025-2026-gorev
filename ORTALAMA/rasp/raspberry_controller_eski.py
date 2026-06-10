import socket
import serial
import time

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

def frame_send_new(stop_event: threading.Event, UDP_IP: int, UDP_PORT: 9999):
    CHUNK_SIZE = 1400                      # ~ MTU altı
    HEADER_FMT = '<LHB'                   # frame_id:uint32, chunk_id:uint16, is_last:uint8

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # PiCamera2'yi başlat ve yapılandır
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    picam2.start()
    time.sleep(2)  # Kamera başlatma süresi için bekle

    frame_id = 0
    try:
        print(f"{UDP_IP} adresine gönderim başladı")
        while not stop_event.is_set():
            frame = picam2.capture_array()
            _, buf = cv2.imencode('.jpg', frame)
            data = buf.tobytes()
            total_chunks = ceil(len(data) / CHUNK_SIZE)

            for chunk_id in range(total_chunks):
                start = chunk_id * CHUNK_SIZE
                end = start + CHUNK_SIZE
                chunk = data[start:end]
                is_last = 1 if chunk_id == total_chunks - 1 else 0
                header = struct.pack(HEADER_FMT, frame_id, chunk_id, is_last)
                sock.sendto(header + chunk, (UDP_IP, UDP_PORT))

            frame_id = (frame_id + 1) & 0xFFFFFFFF

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Ctrl+C ile çıkıldı.")

    finally:
        # Kamera ve soketi kapat
        print("Program sonlandırıldı.")
        picam2.stop()
        sock.close()

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


def main(stop_event: threading.Event):
    threading.Thread(target=start_sender, daemon=True, args=(stop_event, )).start()
    #threading.Thread(target=frame_send_new, daemon=True, args=(stop_event, "172.16.13.53", 9999)).start()
    # Seri port bağlantısını kur
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Seri port açıldı: {SERIAL_PORT} @ {BAUD_RATE}")
        time.sleep(2)  # Arduino'nun resetlenmesi için bekle
    except Exception as e:
        print(f"Seri port açılamadı: {e}")
        # Eğer /dev/ttyACM0 yoksa /dev/ttyUSB0 dene (alternatif)
        try:
            ser = serial.Serial('/dev/ttyUSB0', BAUD_RATE, timeout=1)
            print(f"Seri port açıldı: /dev/ttyUSB0 @ {BAUD_RATE}")
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
                    data_bytes = conn.recv(BUFFER_SIZE)
                    if not data_bytes:
                        print("İstemci bağlantıyı kapattı.")
                        break

                    # Alınan veriyi string'e dönüştür (utf-8)
                    try:
                        data_str = data_bytes.decode('utf-8').strip()
                        print(f"Alınan veri (TCP String): {data_str}")

                        # String veriyi tekrar byte formatına çevirip Arduino'ya gönder
                        if ser is not None:
                            ser.write((data_str + '\n').encode('utf-8'))
                            print(f"'{data_str}' verisi Arduino'ya iletildi.")
                    except UnicodeDecodeError:
                        print("Gelen veri utf-8 formatında çözülemedi, ham veri gönderiliyor.")
                        if ser is not None:
                            ser.write(data_bytes)

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