import asyncio
import json
import socket
import struct
import time
from src.network.packet import ArchipelPacket, PacketType

MULTICAST_GROUP = '239.255.42.99'
MULTICAST_PORT = 6000
HELLO_INTERVAL = 30  # secondes

class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, node_identity, tcp_port, peer_table):
        self.identity = node_identity
        self.tcp_port = tcp_port
        self.peer_table = peer_table
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"[UDP] Prêt pour la découverte Multicast sur {MULTICAST_GROUP}:{MULTICAST_PORT}")
        # Démarrer la boucle d'émission de HELLO
        asyncio.create_task(self.say_hello_loop())

    def datagram_received(self, data, addr):
        try:
            packet = ArchipelPacket.parse(data)
            
            # Rejeter nos propres paquets
            if packet.node_id == self.identity.public_key_bytes:
                return

            if packet.pkt_type == PacketType.HELLO:
                self.handle_hello(packet, addr)
                
            elif packet.pkt_type == PacketType.PEER_LIST:
                self.handle_peer_list(packet)

        except ValueError as e:
            # Paquet invalide ignoré
            pass
        except Exception as e:
            print(f"[UDP] Erreur lors de la réception d'un paquet: {e}")

    def handle_hello(self, packet: ArchipelPacket, addr: tuple):
        # Payload attendu d'un HELLO: timestamp (8 bytes) + tcp_port (2 bytes)
        if len(packet.payload) != 10:
            return
            
        timestamp, tcp_port = struct.unpack("!Q H", packet.payload)
        ip = addr[0]
        node_id_hex = packet.node_id.hex()
        
        # Mettre à jour la table des pairs
        is_new = self.peer_table.update_peer(
            node_id=packet.node_id, 
            ip=ip, 
            tcp_port=tcp_port
        )
        
        if is_new:
            print(f"👋 Nouveau nœud découvert ! {node_id_hex[:8]}... à {ip}:{tcp_port}")
            asyncio.create_task(self._send_peer_list(ip, tcp_port))

    async def say_hello_loop(self):
        while True:
            try:
                # Création payload: timestamp (Q: uint64) + tcp_port (H: uint16)
                timestamp = int(time.time() * 1000)
                payload = struct.pack("!Q H", timestamp, self.tcp_port)
                
                packet = ArchipelPacket(
                    pkt_type=PacketType.HELLO,
                    node_id=self.identity.public_key_bytes,
                    payload=payload
                )
                
                # Signature du paquet (TODO: l'énoncé de la spec pour le HELLO de base mentionnait une signature ?
                # Par précaution on signe toujours l'en-tête + le payload selon packet.py)
                packet.signature = self.identity.sign(packet.data_to_sign())
                
                # Émission multicast
                self.transport.sendto(packet.serialize(), (MULTICAST_GROUP, MULTICAST_PORT))
            except Exception as e:
                print(f"[UDP] Erreur lors de l'envoi de HELLO: {e}")
                
            await asyncio.sleep(HELLO_INTERVAL)

    async def _send_peer_list(self, ip: str, tcp_port: int) -> None:
        peers_payload = {"peers": []}
        for peer in self.peer_table.get_active_peers():
            peers_payload["peers"].append({
                "node_id": peer["node_id"].hex(),
                "ip": peer["ip"],
                "tcp_port": peer["tcp_port"],
                "last_seen": peer["last_seen"],
                "shared_files": peer.get("shared_files", []),
                "reputation": peer.get("reputation", 0.0),
            })
        payload = json.dumps(peers_payload, separators=(",", ":")).encode("utf-8")
        packet = ArchipelPacket(PacketType.PEER_LIST, self.identity.public_key_bytes, payload)
        packet.signature = self.identity.sign(packet.data_to_sign())
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(packet.serialize(), (ip, MULTICAST_PORT))
        except Exception as exc:
            print(f"[UDP] Échec envoi PEER_LIST à {ip}:{tcp_port} — {exc}")

    def handle_peer_list(self, packet: ArchipelPacket) -> None:
        try:
            payload = json.loads(packet.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return
        for entry in payload.get("peers", []):
            try:
                node_id = bytes.fromhex(entry["node_id"])
                ip = entry["ip"]
                tcp_port = int(entry["tcp_port"])
            except (KeyError, ValueError):
                continue
            self.peer_table.update_peer(node_id=node_id, ip=ip, tcp_port=tcp_port)

def get_local_ip() -> str:
    """Détermine l'adresse IP de l'interface réseau active."""
    try:
        # Création d'un socket UDP bidon pour forcer l'OS à choisir l'interface active.
        # N'envoie rien de réel, ne nécessite pas d'internet.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1)) 
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '0.0.0.0'

def create_multicast_socket() -> socket.socket:
    """Crée et configure une socket UDP prête pour le multicast sur réseau hors-ligne."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    local_ip = get_local_ip()
    print(f"[UDP] Interface réseau local détectée: {local_ip}")
    
    # Pour Windows, on bind généralement sur ''
    try:
        sock.bind(('', MULTICAST_PORT))
    except Exception as e:
        print(f"[Erreur Multicast Bind] Impossible de bind ({e}). On essaie {local_ip}.")
        sock.bind((local_ip, MULTICAST_PORT))

    # Au lieu de INADDR_ANY, on se binde explicitement sur l'IP locale pour que 
    # le multicast fonctionne SANS internet (sinon Windows ne sait pas où router).
    if local_ip != '0.0.0.0':
        mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(local_ip)
        # Spécifie explicitement l'interface de SORTIE des paquets multicast
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
    else:
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)

    # Rejoindre le groupe multicast de réception sur l'interface locale
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    # Restreindre le TTL du multicast au LAN local
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    
    # Recevoir ses propres messages ou non
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    return sock
