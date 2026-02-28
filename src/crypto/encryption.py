import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class SecureChannel:
    """
    Gère le chiffrement symétrique et l'authentification avec AES-256-GCM.
    Un nonce de 96 bits (12 bytes) généré aléatoirement est utilisé pour chaque message.
    """
    def __init__(self, session_key: bytes):
        if len(session_key) != 32:
            raise ValueError("La clé de session AES-256-GCM doit faire exactement 32 bytes.")
        self.aesgcm = AESGCM(session_key)

    def encrypt_message(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """
        Chiffre un message avec AES-256-GCM.
        Retourne un tuple: (nonce [12 bytes], ciphertext_with_tag)
        Le format de cryptographie (AESGCM) attache le tag d'authentification de 16 octets à la fin du ciphertext.
        """
        # Générer un nonce très sécurisé pour GCM (96 bits)
        nonce = os.urandom(12)
        
        # aesgcm.encrypt retourne: ciphertext + 16 bytes auth tag concaténés
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, associated_data=None)
        
        return nonce, ciphertext

    def decrypt_message(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        Déchiffre et vérifie l'authenticité d'un message avec AES-256-GCM.
        Levez une exception InvalidTag (ou autre) si le message a été altéré ou la clé est erronée.
        """
        if len(nonce) != 12:
            raise ValueError("Le nonce AES-GCM doit faire 12 bytes.")
            
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, associated_data=None)
            return plaintext
        except Exception as e:
            # L'exception cryptography.exceptions.InvalidTag est levée, on peut logger l'erreur.
            raise ValueError(f"Échec du déchiffrement: altération détectée ou mauvaise clé. {e}")
