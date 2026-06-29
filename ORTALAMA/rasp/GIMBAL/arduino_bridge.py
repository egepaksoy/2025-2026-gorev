import socket
import serial
import time

# --- Yapılandırma ---
# TCP Ayarları
TCP_IP = '0.0.0.0'  # Tüm arayüzlerden dinle
TCP_PORT = 5005     # Dinlenecek port
BUFFER_SIZE = 1024  # Her seferinde okunacak maksimum bayt

# Seri Port (Arduino) Ayarları
# Raspberry Pi'de Arduino genellikle /dev/ttyACM0 veya /dev/ttyUSB0 olarak görünür.
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600    # Arduino tarafındaki Serial.begin(9600) ile aynı olmalı

def main():
    connection_closed = False
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
        while not connection_closed:
            print("Yeni bir bağlantı bekleniyor...")
            conn, addr = server_socket.accept()
            print(f"Bağlantı kabul edildi: {addr}")

            with conn:
                while not connection_closed:
                    while not connection_closed:
                        data_bytes = conn.recv(BUFFER_SIZE)
                        if not data_bytes:
                            print("İstemci bağlantıyı kapattı.")
                            connection_closed = True
                            break

                        # Alınan veriyi string'e dönüştür (utf-8)
                        try:
                            data_str = data_bytes.decode('utf-8').strip()
                            print(f"Alınan veri (TCP String): {data_str}")

                            # String veriyi tekrar byte formatına çevirip Arduino'ya gönder
                            # Sonuna satır sonu karakteri (\n) eklemek Arduino tarafında okumayı kolaylaştırır
                            if ser is not None:
                                ser.write((data_str + '\n').encode('utf-8'))
                            print(f"'{data_str}' verisi Arduino'ya iletildi.")
                        except UnicodeDecodeError:
                            print("Gelen veri utf-8 formatında çözülemedi, ham veri gönderiliyor.")
                            ser.write(data_bytes)

    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Bir hata oluştu: {e}")
    finally:
        server_socket.close()
        if ser is not None:
            ser.close()
        print("Bağlantılar kapatıldı.")

if __name__ == "__main__":
    main()