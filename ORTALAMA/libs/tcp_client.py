# TCP İle gimbal hareketi icin
import socket, threading, time

class TCPClient:
    def __init__(self, host='127.0.0.1', port=5005):
        self.host = host
        self.port = port
        self.client_socket = None

        self.connected = False

        self.data = None
        self.data_lock = threading.Lock()

        self.connect()
        
        #self.tested = self.test()
        self.tested = True

    def connect(self):
        """Sunucuya bağlantı kurar."""
        try:
            if not self.connected:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.host, self.port))
                print(f"Sunucuya ({self.host}:{self.port}) bağlandı.")
                self.connected = True
                threading.Thread(target=self.receive_data, daemon=True).start()
                return True
            else:
                print("Sistem sunucuya bagli")
        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            self.connected = False
            return False

    def send_data(self, data):
        """Veriyi string veya byte formatında gönderir."""
        if not self.client_socket:
            print("Bağlantı yok. Lütfen önce connect() metodunu çağırın.")
            return False
        
        try:
            # Eğer veri string ise byte formatına çevir
            if isinstance(data, str):
                data = data.strip()
                data += "\n"
                data = data.encode('utf-8')
            
            self.client_socket.sendall(data)
            return True
        except Exception as e:
            print(f"Veri gönderilirken hata oluştu: {e}")
            return False

    def receive_data(self, buffer_size=1024):
        print("Veri dinleme baslatildi")
        while self.connected:
            try:
                data = self.client_socket.recv(buffer_size).decode()
                if data:
                    with self.data_lock:
                        self.data = data

            except Exception as e:
                print(f"Client>> Receive failed: {e}")
                break
        
            time.sleep(0.05)

    def get_data(self):
        with self.data_lock:
            data = self.data
            self.data = None
        return data

    def test(self):
        try:
            self.connect()
            self.send_data("fizz")
            time.sleep(0.5)
            recieved_data = self.get_data()
            while recieved_data is None:
                recieved_data = self.get_data()
                time.sleep(0.05)
            if recieved_data is not None:
                print(f"[TEST]>> TCP Test basarili")
                return True
            print(f"[TEST]>> TCP Test basarisiz veri gelmedi")
            return False
        except Exception as e:
            print(f"[TEST]>> TCP Test basarisiz: {e}")
            return False
    
    def reset_pos(self):
        self.send_data("zero")

    def close(self):
        """Bağlantıyı kapatır."""
        self.reset_pos()
        if self.client_socket:
            self.client_socket.close()
            self.connected = False
            print("Bağlantı kapatıldı.")
