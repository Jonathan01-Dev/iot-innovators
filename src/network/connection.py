import asyncio
import struct
import hashlib
from src.network.packet import ArchipelPacket, PacketType
from src.crypto.session import SecureSession
from src.crypto.encryption import SecureChannel
from src.crypto.pki import NodeIdentity
from src.core.wot import WebOfTrust

class ArchipelConnection:
    """
    Gestionnaire d'une connexion TCP asynchrone chiffrée de bout en bout
    utilisant le Handshake "Noise-like".
    """
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, identity, wot: WebOfTrust):
        self.reader = reader
        self.writer = writer
        self.identity = identity
        self.wot = wot
        self.peer_node_id = None
        
        self.session = SecureSession()
        self.channel = None  # Instancié après le Handshake
        self.is_authenticated = False

    async def _send_packet(self, packet: ArchipelPacket):
        data = packet.serialize()
        self.writer.write(data)
        await self.writer.drain()

    async def _receive_packet(self) -> ArchipelPacket:
        # Lecture de l'en-tête (43 octets par ex)
        header_data = await self.reader.readexactly(ArchipelPacket.HEADER_SIZE)
        magic, pkt_type, node_id, payload_len = struct.unpack(ArchipelPacket.HEADER_FORMAT, header_data)
        
        # Lecture du payload + signature (64 bytes)
        rest_of_data = await self.reader.readexactly(payload_len + 64)
        return ArchipelPacket.parse(header_data + rest_of_data)

    async def send_encrypted_message(self, plaintext: bytes):
        if not self.is_authenticated:
            raise ValueError("Le handshake n'est pas terminé.")
            
        nonce, ciphertext = self.channel.encrypt_message(plaintext)
        payload = nonce + ciphertext
        
        packet = ArchipelPacket(PacketType.MSG, self.identity.public_key_bytes, payload)
        packet.signature = self.identity.sign(packet.data_to_sign())
        await self._send_packet(packet)

    async def receive_encrypted_message(self) -> bytes:
        packet = await self._receive_packet()
        if packet.pkt_type != PacketType.MSG:
            raise ValueError("Paquet MSG attendu")

        if not NodeIdentity.verify(packet.node_id, packet.data_to_sign(), packet.signature):
            raise ValueError("Signature de paquet invalide")

        nonce = packet.payload[:12]
        ciphertext = packet.payload[12:]
        return self.channel.decrypt_message(nonce, ciphertext)

    async def do_server_handshake(self):
        """Logique côté Serveur (Bob) lorsqu'un client se connecte."""
        # 1. Lire HELLO_TCP (e_A_pub)
        packet1 = await self._receive_packet()
        if packet1.pkt_type != PacketType.HELLO:
            raise ValueError("Erreur Handshake: Paquet HELLO attendu.")
            
        alice_e_pub = packet1.payload
        self.peer_node_id = packet1.node_id
        
        # Vérification Web of Trust (TOFU)
        if not self.wot.verify_node(self.peer_node_id.hex()):
            self.writer.close()
            raise ValueError("Nœud refusé par le Web of Trust.")
            
        # 2. Calculer le secret
        bob_e_pub = self.session.get_public_bytes()
        self.session.compute_shared_secret(alice_e_pub)
        
        # 3. Répondre HELLO_REPLY (e_B_pub + signature de Bob)
        # La signature porte sur la concaténation de (e_A_pub + e_B_pub)
        data_to_sign = alice_e_pub + bob_e_pub
        sig_B = self.identity.sign(data_to_sign)
        
        packet2 = ArchipelPacket(PacketType.HELLO_REPLY, self.identity.public_key_bytes, bob_e_pub + sig_B)
        packet2.signature = self.identity.sign(packet2.data_to_sign())
        await self._send_packet(packet2)
        
        # 4. Attendre AUTH de Alice
        packet3 = await self._receive_packet()
        if packet3.pkt_type != PacketType.AUTH:
            raise ValueError("Erreur Handshake: Paquet AUTH attendu.")
            
        sig_A = packet3.payload
        # Vérification de la signature d'Alice sur le shared_secret_hash + eB etc.
        data_to_sign_alice = alice_e_pub + bob_e_pub + hashlib.sha256(self.session._shared_key).digest()
        
        if not self.identity.verify(self.peer_node_id, data_to_sign_alice, sig_A):
            raise ValueError("Signature d'authentification (AUTH) invalide.")
            
        # 5. Envoyer AUTH_OK et initialiser le SecureChannel
        packet4 = ArchipelPacket(PacketType.AUTH_OK, self.identity.public_key_bytes, b'OK')
        packet4.signature = self.identity.sign(packet4.data_to_sign())
        await self._send_packet(packet4)
        
        self.channel = SecureChannel(self.session.session_key)
        self.is_authenticated = True
        print(f"[TCP] Handshake terminé. Tunnel AES-256-GCM actif avec {self.peer_node_id.hex()[:8]}")

    async def connect_and_do_client_handshake(self, ip: str, port: int):
        """Logique côté Client (Alice) qui initie la connexion."""
        print(f"    [TCP] (Client) asyncio.open_connection à {ip}:{port}...")
        self.reader, self.writer = await asyncio.open_connection(ip, port)
        print("    [TCP] (Client) Connexion TCP établie.")
        
        # 1. Envoyer HELLO_TCP
        print("    [TCP] (Client) Envoi HELLO...")
        alice_e_pub = self.session.get_public_bytes()
        packet1 = ArchipelPacket(PacketType.HELLO, self.identity.public_key_bytes, alice_e_pub)
        packet1.signature = self.identity.sign(packet1.data_to_sign())
        await self._send_packet(packet1)
        
        # 2. Lire HELLO_REPLY (e_B_pub + sig_B)
        print("    [TCP] (Client) Attente HELLO_REPLY...")
        packet2 = await self._receive_packet()
        print("    [TCP] (Client) Reçu paquet type:", packet2.pkt_type)
        if packet2.pkt_type != PacketType.HELLO_REPLY:
            raise ValueError(f"Erreur Handshake: Paquet HELLO_REPLY attendu, reçu {packet2.pkt_type}")
            
        bob_e_pub = packet2.payload[:32]
        sig_B = packet2.payload[32:]
        self.peer_node_id = packet2.node_id
        
        # Vérification WoT
        print("    [TCP] (Client) WoT verify...")
        if not self.wot.verify_node(self.peer_node_id.hex()):
            self.writer.close()
            raise ValueError("Nœud serveur refusé par le Web of Trust.")
            
        # Vérifier sig_B
        print("    [TCP] (Client) Vérification signature serveur...")
        if not self.identity.verify(self.peer_node_id, alice_e_pub + bob_e_pub, sig_B):
            raise ValueError("Signature du serveur invalide (Man-in-the-middle).")
            
        # 3. Calcul du secret
        print("    [TCP] (Client) Calcul shared secret...")
        self.session.compute_shared_secret(bob_e_pub)
        
        # 4. Envoi AUTH
        print("    [TCP] (Client) Envoi AUTH...")
        data_to_sign_alice = alice_e_pub + bob_e_pub + hashlib.sha256(self.session._shared_key).digest()
        sig_A = self.identity.sign(data_to_sign_alice)
        packet3 = ArchipelPacket(PacketType.AUTH, self.identity.public_key_bytes, sig_A)
        packet3.signature = self.identity.sign(packet3.data_to_sign())
        await self._send_packet(packet3)
        
        # 5. Attente AUTH_OK
        print("    [TCP] (Client) Attente AUTH_OK...")
        packet4 = await self._receive_packet()
        print("    [TCP] (Client) Reçu paquet type:", packet4.pkt_type)
        if packet4.pkt_type != PacketType.AUTH_OK:
            raise ValueError("Erreur Handshake: Serveur n'a pas confirmé l'AUTH.")
            
        self.channel = SecureChannel(self.session.session_key)
        self.is_authenticated = True
        print(f"[TCP] Handshake terminé. Tunnel AES-256-GCM actif avec serveur {self.peer_node_id.hex()[:8]}")
