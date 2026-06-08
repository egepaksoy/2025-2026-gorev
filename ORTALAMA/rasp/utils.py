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
        self.conn, self.server_socket = None, None
    
    def connect(self):
        try:
            # TCP Soketi oluştur
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Portu hemen tekrar kullanılabilir yap
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)

            print(f"[TCP]>> TCP Sunucusu başlatıldı. {self.host}:{self.port} portu dinleniyor...")
            
            print("[TCP]>> Yeni bir bağlantı bekleniyor...")
            while not self.stop_event.is_set():
                try:
                    server_socket.settimeout(1.0) # stop_event kontrolü için periyodik timeout
                    conn, addr = server_socket.accept()
                except socket.timeout:
                    continue
            
                print(f"[TCP]>> Bağlantı kabul edildi: {addr}")
                break

            if self.stop_event.is_set() and conn is None:
                self.close()
                return None, None

            self.conn, self.server_socket = conn, server_socket
            self.connected = True
            self.start_receiver()
            return conn, server_socket
        
        except Exception as e:
            print(f"[TCP]>> TCP Baglanti hatası: {e}")
    
    def start_receiver(self):
        threading.Thread(target=self.receive_data, daemon=True).start()

    def receive_data(self):
        if not self.connected:
            print("[TCP]>> Connect metodu cagirilmamis")
            exit(1)
        try:
            print("[TCP]>> Listener baslatildi.")
            while not self.stop_event.is_set():
                data_bytes = self.conn.recv(self.BUFFER_SIZE)
                if not data_bytes:
                    print("[TCP]>> İstemci bağlantıyı kapattı.")
                    break
                
                # Gelen veriyi çöz (unpack)
                data_str = data_bytes.decode('utf-8').strip()
                with self.data_lock:
                    self.data = data_str
                
                time.sleep(0.05)
                
        except ConnectionResetError:
            print("[TCP]>> İstemci bağlantıyı kesti.")
        finally:
            if self.connected:
                self.close()
    
    def send_data(self, data: str):
        if self.connected and self.conn:
            try:
                self.conn.sendall(data.encode())
            except OSError:
                print("[TCP]>> Veri gönderilemedi, soket kapalı.")
    
    def get_data(self):
        data = None
        with self.data_lock:
            data = self.data
            self.data = None
        return data

    def close(self):
        self.connected = False
        # Soketleri kapatırken None kontrolü yapmak ve try-except kullanmak çökmenin önüne geçer
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass
        print("[TCP]>> Soketler güvenli bir şekilde kapatıldı.")


class VIDEO_HANDLER:
    def __init__(self, host: str="0.0.0.0", port: int=9999, stop_event: threading.Event=None):
        self.host = host
        self.port = port
        
        if stop_event is None:
            stop_event = threading.Event()
        self.stop_event = stop_event

        self.connected = False
        self.client_socket, self.picam2, self.server_socket = None, None, None
    
    def connect(self):
        if self.connected:
            print("[UDP]>> Video Zaten bagli")
            return self.client_socket, self.picam2, self.server_socket

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
            print(f"[UDP]>> Gönderici {self.port} portunda bekleniyor (Picamera2 aktif)...")

            client_socket, addr = server_socket.accept()
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Nagle algoritmasını devre dışı bırak
            print(f"[UDP]>> Alıcı bağlandı: {addr}")

            self.client_socket, self.picam2, self.server_socket = client_socket, picam2, server_socket
            self.connected = True
            self.start_sender()
            return client_socket, picam2, server_socket

        except Exception as e:
            print(f"[UDP]>> Kamera baglanti hatasi: {e}")
            
    def start_sender(self):
        threading.Thread(target=self.sender, daemon=True).start()

    def sender(self):
        if not self.connected:
            self.client_socket, self.picam2, self.server_socket = self.connect()
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
            print(f"[UDP]>> Kamera/Gönderici Hatası: {e}")
        finally:
            self.close()
            print("[UDP]>> Kamera ve bağlantı kapatıldı.")
    
    def close(self):
        if self.connected:
            self.picam2.stop()
            self.client_socket.close()
            self.server_socket.close()
            self.connected = False

class ARDUINO_HANDLER:
    def __init__(self, serial_port: str='/dev/ttyUSB0', baud_rate: int=9600, stop_event: threading.Event=None):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        
        if stop_event is None:
            stop_event = threading.Event()
        self.stop_event = stop_event

        self.ser_lock = threading.Lock()
        self.ser_value = None  # En güncel veri burada tutulacak

        self.connected = False
        self.ser = None
    
    def connect(self):
        if self.connected:
            print("[SERIAL]>> Arduino zaten bagli")
            return self.ser

        try:
            ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            ser.write("0|0".encode("utf-8"))
            print(f"[SERIAL]>> Seri port açıldı: {self.serial_port} @ {self.baud_rate}")
            time.sleep(2)  # Arduino'nun resetlenmesi için bekle
        except Exception as e:
            print(f"[SERIAL]>> Seri port açılamadı: {e}")
            try:
                self.serial_port = '/dev/ttyACM0'
                ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
                ser.write("0|0".encode("utf-8"))
                print(f"[SERIAL]>> Seri port açıldı: {self.serial_port} @ {self.baud_rate}")
                time.sleep(2)
            except Exception as e2:
                print(f"[SERIAL]>> Alternatif seri port da açılamadı: {e2}")
                exit(1)
        
        self.ser = ser
        self.connected = True
        
        # --- YENİ: Arka planda sürekli okuma yapacak thread'i başlatıyoruz ---
        threading.Thread(target=self._listen_serial, daemon=True).start()
        return ser

    def _listen_serial(self):
        """Arka planda seri portu sürekli dinleyen metot"""
        print("[SERIAL]>> Dinleyici thread baslatildi.")
        while not self.stop_event.is_set() and self.connected:
            try:
                if self.ser.in_waiting > 0:
                    raw_data = self.ser.readline().decode("utf-8", errors='ignore').strip()
                    if raw_data:  # Boş satır değilse kaydet
                        with self.ser_lock:
                            self.ser_value = raw_data
                else:
                    time.sleep(0.01)  # İşlemciyi yormamak için kısa bekleme
            except Exception as e:
                print(f"[SERIAL]>> Okuma hatası: {e}")
                break

    def get_value(self):
        """Main döngüsünden çağrılacak metot: En son okunan güncel veriyi döner"""
        with self.ser_lock:
            return self.ser_value
    
    def write_value(self, value: str):
        if self.connected and self.ser:
            try:
                self.ser.write((value.strip() + '\n').encode('utf-8'))
            except Exception as e:
                print(f"[SERIAL]>> Yazma hatası: {e}")
    
    def close(self):
        self.connected = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        print("[SERIAL]>> Seri port kapatıldı.")


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
                print("[SERIAL]>> Geçersiz ölçüm alındı, tekrar deneniyor...")
            
        except OSError:
            print("[SERIAL]>> I2C bağlantı hatası! LIDAR bağlı mı?")
            return None  # Bağlantı hatası olursa None döndür

        time.sleep(0.001)  # Sensörün stabilize olması için bekleme süresi
    
    if not distances:
        return None  # Geçerli ölçüm alınamadıysa None döndür

    avg_distance_cm = sum(distances) / len(distances)  # Ölçümleri ortalama alarak hassasiyeti artır
    avg_distance_m = avg_distance_cm / 100  # Metreye çevir

    return round(avg_distance_m, 3)  # Ölçümü metre cinsinden 3 ondalık basamakla döndür