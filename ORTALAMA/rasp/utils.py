# TCP İle gimbal hareketi icin
import socket, threading, time

from picamera2 import Picamera2
import io
import struct

import smbus

import serial


class TCP_HANDLER:
    def __init__(self, host: str="0.0.0.0", port: int=5005, stop_event: threading.Event=None):
        self.host = host
        self.port = port

        if stop_event is None:
            stop_event = threading.Event()
        
        self.stop_event = stop_event

        self.BUFFER_SIZE = 1024

        self.data_lock = threading.Lock()
        self.data = None

        self.connected = False
        self.conn, self.server_socket = self.connect()
    
    def connect(self):
        try:
            # TCP Soketi oluştur
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)

            print(f"Sunucu {self.host}:{self.port} üzerinde dinleniyor...")
            
            conn, addr = server_socket.accept()

            print(f"Bağlantı sağlandı: {addr}")

            self.connected = True
            return conn, server_socket
        
        except Exception as e:
            print(f"TCP Baglanti hatası: {e}")
    
    def start_receiver(self):
        threading.Thread(target=self.receive_data, daemon=True).start()

    def receive_data(self):
        try:
            while self.stop_event.is_set():
                data_bytes = self.conn.recv(self.BUFFER_SIZE)
                if not data_bytes:
                    print("İstemci bağlantıyı kapattı.")
                    break
                
                # Gelen veriyi çöz (unpack)
                data_str = data_bytes.decode('utf-8').strip()
                with self.data_lock:
                    self.data = data_str
                
                time.sleep(0.05)
                
        except ConnectionResetError:
            print("İstemci bağlantıyı kesti.")
        finally:
            self.close()
    
    def send_data(self, data: str):
        self.conn.sendall(data.encode())
    
    def get_data(self):
        data = None
        with self.data_lock:
            data = self.data
            self.data = None
        return data

    def close(self):
        if self.connected:
            self.conn.close()
            self.server_socket.close()
            self.connected = False


class VIDEO_HANDLER:
    def __init__(self, host: str="0.0.0.0", port: int=9999, stop_event: threading.Event=None):
        self.host = host
        self.port = port
        
        if stop_event is None:
            stop_event = threading.Event()
        self.stop_event = stop_event

        self.connected = False
        self.client_socket, self.picam2, self.server_socket = self.connect()
    
    def connect(self):
        try:
            picam2 = Picamera2()
            # Kamera ayarları
            config = picam2.create_video_configuration(main={"size": (640, 480)})
            picam2.configure(config)
            picam2.start()
            
            # Kameranın ısınması için kısa bir bekleme
            time.sleep(2)

            # Sunucu (Alıcı) soketini oluştur
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)
            print(f"Gönderici {self.port} portunda bekleniyor (Picamera2 aktif)...")

            client_socket, addr = server_socket.accept()
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Nagle algoritmasını devre dışı bırak
            print(f"Alıcı bağlandı: {addr}")

            self.connected = True
            return client_socket, picam2, server_socket

        except Exception as e:
            print(f"Kamera baglanti hatasi: {e}")
            
    def start_sender(self):
        threading.Thread(target=self.sender, daemon=True).start()

    def sender(self):
        try:
            stream = io.BytesIO()

            # Sürekli olarak JPEG formatında yakala ve gönder
            while not self.stop_event.is_set():
                stream.seek(0)
                stream.truncate()
                
                # Görüntüyü stream'e JPEG olarak yakala
                self.picam2.capture_file(stream, format='jpeg')
                
                # Verinin boyutunu al
                image_len = stream.tell()
                if image_len > 0:
                    # Önce boyutu (unsigned long), sonra veriyi gönder
                    self.client_socket.sendall(struct.pack(">L", image_len))
                    
                    stream.seek(0)
                    self.client_socket.sendall(stream.read())
                
        except Exception as e:
            print(f"Kamera/Gönderici Hatası: {e}")
        finally:
            self.close()
            print("Kamera ve bağlantı kapatıldı.")
    
    def close(self):
        if self.connected:
            self.picam2.stop()
            self.client_socket.close()
            self.server_socket.close()
            self.connected = False

class AURDUINO_HANDLER:
    def __init__(self, serial_port: str='/dev/ttyUSB0', baud_rate: int=9600, stop_event: threading.Event=None):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        
        if stop_event is None:
            stop_event = threading.Event()
        self.stop_event = stop_event

        self.ser_lock = threading.Lock()
        self.ser_value = None

        self.connected = False
        self.ser = self.connect()
    
    def connect(self):
        try:
            ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            ser.write("0|0".encode("utf-8"))
            print(f"Seri port açıldı: {self.serial_port} @ {self.baud_rate}")
            time.sleep(2)  # Arduino'nun resetlenmesi için bekle
        except Exception as e:
            print(f"Seri port açılamadı: {e}")
            # Eğer /dev/ttyUSB0 yoksa /dev/ttyACM0 dene (alternatif)
            try:
                self.serial_port = '/dev/ttyACM0'
                ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
                ser.write("0|0")
                print(f"Seri port açıldı: {self.serial_port} @ {self.baud_rate}")
                time.sleep(2)
            except Exception as e2:
                print(f"Alternatif seri port da açılamadı: {e2}")
                ser = None
                exit(1)
        
        self.connected = True
        return ser

    def get_value(self):
        if self.ser.in_waiting > 0:
            return str(self.ser.readline().decode("utf-8", errors='ignore')).strip()
        return None
    
    def write_value(self, value: str):
        self.ser.write((value.strip() + '\n').encode('utf-8'))
    
    def close(self):
        self.ser.close()


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