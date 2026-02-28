import struct
import hashlib

# Magic bytes pour Archipel v1
MAGIC_BYTES = b'ARCH'

class PacketType:
    HELLO = 0x01
    PEER_LIST = 0x02
    MSG = 0x03
    CHUNK_REQ = 0x04
    CHUNK_DATA = 0x05
    MANIFEST = 0x06
    ACK = 0x07
    HELLO_REPLY = 0x08
    AUTH = 0x09
    AUTH_OK = 0x0A

class ArchipelPacket:
    """
    Format de paquet Archipel v1
    ┌─────────────────────────────────────────────────────────┐ 
    │  MAGIC   │  TYPE    │  NODE_ID  │  PAYLOAD_LEN          │
    │  4 bytes │  1 byte  │  32 bytes │  4 bytes (uint32_BE)  │ 
    ├──────────┴──────────┴───────────┴────────────────────── │ 
    │  PAYLOAD (chiffré, longueur variable)                   │
    ├──────────────────────────────────────────────────────── │ 
    │  HMAC-SHA256 SIGNATURE  (32 bytes)                      │
    └─────────────────────────────────────────────────────────┘ 
    """
    HEADER_FORMAT = "!4s B 32s I"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, pkt_type: int, node_id: bytes, payload: bytes, signature: bytes = b''):
        if len(node_id) != 32:
            raise ValueError("node_id doit faire exactement 32 octets (Ed25519 public key)")
        
        self.pkt_type = pkt_type
        self.node_id = node_id
        self.payload = payload
        self.signature = signature

    def serialize(self) -> bytes:
        """Sérialise l'en-tête et le payload."""
        header = struct.pack(
            self.HEADER_FORMAT,
            MAGIC_BYTES,
            self.pkt_type,
            self.node_id,
            len(self.payload)
        )
        # La signature est ajoutée à la toute fin
        return header + self.payload + self.signature

    @classmethod
    def parse(cls, data: bytes) -> 'ArchipelPacket':
        """Parse un flux d'octets et retourne un ArchipelPacket."""
        if len(data) < cls.HEADER_SIZE + 64: # header + signature
            raise ValueError("Données insuffisantes pour un paquet Archipel valide")

        header_bytes = data[:cls.HEADER_SIZE]
        magic, pkt_type, node_id, payload_len = struct.unpack(cls.HEADER_FORMAT, header_bytes)

        if magic != MAGIC_BYTES:
            raise ValueError(f"Magic bytes invalides: {magic}")

        expected_total_len = cls.HEADER_SIZE + payload_len + 64
        if len(data) < expected_total_len:
            raise ValueError(f"Payload tronqué. Attendu: {expected_total_len}, reçu: {len(data)}")

        payload = data[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_len]
        signature = data[cls.HEADER_SIZE + payload_len:expected_total_len]

        return cls(pkt_type, node_id, payload, signature)

    def data_to_sign(self) -> bytes:
        """Retourne les octets exacts sur lesquels la signature ou le MAC doit s'appliquer."""
        header = struct.pack(
            self.HEADER_FORMAT,
            MAGIC_BYTES,
            self.pkt_type,
            self.node_id,
            len(self.payload)
        )
        return header + self.payload

