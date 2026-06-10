# Deneme kutuphanesi
import socket
import struct

def start_server(host='0.0.0.0', port=5005):
    # TCP Soketi oluştur
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    
    print(f"Sunucu {host}:{port} üzerinde dinleniyor...")
    
    conn, addr = server_socket.accept()

    print(f"Bağlantı sağlandı: {addr}")
    
    try:
        while True:
            # 2 adet integer (her biri 4 byte, toplam 8 byte) bekliyoruz
            data = conn.recv(8)
            if not data:
                break
            
            # Gelen veriyi çöz (unpack)
            # '!ii' formatı: ! -> network byte order, i -> integer
            x_axis, y_axis = struct.unpack('!ii', data)
            
            print(f"Alınan Veriler -> X Ekseni: {x_axis}, Y Ekseni: {y_axis}")
            
            # Burada servo kontrol fonksiyonlarını çağırabilirsin
            
    except ConnectionResetError:
        print("İstemci bağlantıyı kesti.")
    finally:
        conn.close()
        server_socket.close()

if __name__ == "__main__":
    start_server()
