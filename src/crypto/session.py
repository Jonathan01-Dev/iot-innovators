import os
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

class SecureSession:
    """
    Gère un échange de clé X25519 éphémère et la dérivation avec HKDF-SHA256
    pour aboutir à une clé de session AES-256-GCM.
    """
    def __init__(self):
        # Clé asymétrique éphémère (valable uniquement le temps de la session)
        self._private_key = x25519.X25519PrivateKey.generate()
        self._shared_key = None
        self.session_key = None
        
    @property
    def public_key_bytes(self) -> bytes:
        """La clé publique éphémère (32 bytes) à envoyer dans le HELLO_REPLY."""
        return self._private_key.public_key().public_bytes(
            encoding=None, # Raw bytes since x25519 doesn't use DER for raw exchange
            format=None    # See below for actual cryptography API behavior
        )

    def get_public_bytes(self) -> bytes:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return self._private_key.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw
        )

    def compute_shared_secret(self, peer_public_bytes: bytes):
        """Calcule le secret partagé à partir de la clé publique éphémère du pair."""
        peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
        self._shared_key = self._private_key.exchange(peer_public_key)
        self._derive_session_key()

    def _derive_session_key(self):
        """Dérive la clé AES (32 bytes = 256 bits) avec HKDF-SHA256."""
        if not self._shared_key:
            raise ValueError("Le secret partagé n'a pas été calculé.")
            
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32, # 256 bits pour AES-256
            salt=None,
            info=b'archipel-v1'
        )
        self.session_key = hkdf.derive(self._shared_key)
