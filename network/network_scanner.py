import scapy.all as scapy
import socket

def get_local_ip():
    """현재 내 PC의 로컬 IP 대역을 가져옵니다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def scan(ip_range):
    """지정한 IP 대역을 스캔하여 연결된 장치를 찾습니다."""
    print(f"📡 스캔 시작: {ip_range}")
    
    # ARP 요청 패킷 생성
    arp_request = scapy.ARP(pdst=ip_range)
    broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast/arp_request
    
    # 패킷 전송 및 응답 수신
    answered_list = scapy.srp(arp_request_broadcast, timeout=1, verbose=False)[0]

    clients_list = []
    for element in answered_list:
        client_dict = {"ip": element[1].psrc, "mac": element[1].hwsrc}
        clients_list.append(client_dict)
    return clients_list

if __name__ == "__main__":
    # 내 IP가 192.168.0.x 라면 192.168.0.1/24 대역 스캔
    local_ip = get_local_ip()
    ip_parts = local_ip.split('.')
    target_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1/24"
    
    results = scan(target_ip)
    
    print("-" * 40)
    print("IP 주소\t\t\tMAC 주소")
    print("-" * 40)
    for client in results:
        print(f"{client['ip']}\t\t{client['mac']}")