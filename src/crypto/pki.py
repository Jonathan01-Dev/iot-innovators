import os
from nacl.signing import SigningKey, VerifyKey
import nacl.encoding

class NodeIdentity:
    def __init__(self, key_path: str = '.archipel/identity.key'):
        self.key_path = key_path
        self._signing_key = None
        
    def load_or_generate(self) -> SigningKey:
        """Charge la clé privée depuis le disque, ou en génère une nouvelle s'il n'y en a pas."""
        if os.path.exists(self.key_path):
            with open(self.key_path, 'rb') as f:
                seed = f.read()
                self._signing_key = SigningKey(seed)
        else:
            print("[PKI] Génération d'une nouvelle clé Ed25519 pour ce nœud...")
            self._signing_key = SigningKey.generate()
            self._save()
        return self._signing_key
        
    def _save(self):
        """Sauvegarde la seed (clé privée) sur le disque."""
        dir_name = os.path.dirname(self.key_path)
        if dir_name:  # only create if there's a directory component
            os.makedirs(dir_name, exist_ok=True)
        # La seed de nacl SigningKey est la représentation brute de la clé privée de 32 octets.
        with open(self.key_path, 'wb') as f:
            f.write(self._signing_key.encode())
            
    @property
    def public_key_bytes(self) -> bytes:
        """Retourne la clé publique sous forme d'octets bruts (32 bytes)."""
        if not self._signing_key:
            self.load_or_generate()
        return self._signing_key.verify_key.encode()

    @property
    def public_key_hex(self) -> str:
        """Retourne la clé publique au format hexadécimal."""
        return self.public_key_bytes.hex()
        
    def sign(self, message: bytes) -> bytes:
        """Signe un message et retourne la signature (64 bytes)."""
        if not self._signing_key:
            self.load_or_generate()
        # nacl_sign retourne un objet SignedMessage, on veut juste la signature locale
        signed = self._signing_key.sign(message)
        return signed.signature

    @staticmethod
    def verify(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
        """Vérifie la signature d'un message avec la clé publique fournie."""
        try:
            verify_key = VerifyKey(public_key_bytes)
            # nacl.exceptions.BadSignatureError est levée si la signature est invalide
            verify_key.verify(message, signature)
            return True
        except Exception:
            return False
