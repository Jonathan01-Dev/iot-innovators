"""
Tests unitaires — Cryptographie Archipel
"""
import unittest
import os
import sys

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crypto.pki import NodeIdentity
from src.crypto.session import SecureSession
from src.crypto.encryption import SecureChannel


class TestNodeIdentity(unittest.TestCase):
    """Tests pour la génération de clés Ed25519."""
    
    def setUp(self):
        self.key_path = ".test_identity.key"
        self.identity = NodeIdentity(self.key_path)
        self.identity.load_or_generate()

    def tearDown(self):
        if os.path.exists(self.key_path):
            os.remove(self.key_path)

    def test_key_generation(self):
        """Vérifie que la clé publique fait 32 bytes."""
        self.assertEqual(len(self.identity.public_key_bytes), 32)

    def test_key_persistence(self):
        """Vérifie que la clé est persistée et rechargée identique."""
        pub_hex_1 = self.identity.public_key_hex
        identity2 = NodeIdentity(self.key_path)
        identity2.load_or_generate()
        self.assertEqual(pub_hex_1, identity2.public_key_hex)

    def test_sign_and_verify(self):
        """Vérifie que la signature est valide."""
        msg = b"Hello Archipel"
        sig = self.identity.sign(msg)
        self.assertEqual(len(sig), 64)
        self.assertTrue(NodeIdentity.verify(self.identity.public_key_bytes, msg, sig))

    def test_verify_wrong_message(self):
        """Vérifie qu'une signature invalide est détectée."""
        sig = self.identity.sign(b"Original")
        self.assertFalse(NodeIdentity.verify(self.identity.public_key_bytes, b"Tampered", sig))


class TestSecureSession(unittest.TestCase):
    """Tests pour l'échange de clé X25519 + HKDF."""
    
    def test_key_exchange(self):
        """Deux sessions doivent dériver la même clé de session."""
        alice = SecureSession()
        bob = SecureSession()
        
        alice_pub = alice.get_public_bytes()
        bob_pub = bob.get_public_bytes()
        
        alice.compute_shared_secret(bob_pub)
        bob.compute_shared_secret(alice_pub)
        
        self.assertEqual(alice.session_key, bob.session_key)
        self.assertEqual(len(alice.session_key), 32)


class TestSecureChannel(unittest.TestCase):
    """Tests pour le chiffrement AES-256-GCM."""
    
    def setUp(self):
        alice = SecureSession()
        bob = SecureSession()
        alice.compute_shared_secret(bob.get_public_bytes())
        bob.compute_shared_secret(alice.get_public_bytes())
        self.alice_channel = SecureChannel(alice.session_key)
        self.bob_channel = SecureChannel(bob.session_key)

    def test_encrypt_decrypt(self):
        """Chiffrement puis déchiffrement doivent retourner le message original."""
        plaintext = "Bonjour depuis Archipel ! 🏝️".encode('utf-8')
        nonce, ciphertext = self.alice_channel.encrypt_message(plaintext)
        
        decrypted = self.bob_channel.decrypt_message(nonce, ciphertext)
        self.assertEqual(decrypted, plaintext)

    def test_ciphertext_differs_from_plaintext(self):
        """Le ciphertext ne doit pas contenir le plaintext."""
        plaintext = b"Secret message"
        nonce, ciphertext = self.alice_channel.encrypt_message(plaintext)
        self.assertNotIn(plaintext, ciphertext)

    def test_unique_nonces(self):
        """Deux chiffrements du même message doivent produire des nonces différents."""
        msg = b"Same message"
        nonce1, _ = self.alice_channel.encrypt_message(msg)
        nonce2, _ = self.alice_channel.encrypt_message(msg)
        self.assertNotEqual(nonce1, nonce2)

    def test_tampered_ciphertext(self):
        """Un ciphertext altéré doit lever une erreur."""
        nonce, ciphertext = self.alice_channel.encrypt_message(b"Hello")
        tampered = bytes([b ^ 0xFF for b in ciphertext])
        with self.assertRaises(ValueError):
            self.bob_channel.decrypt_message(nonce, tampered)


if __name__ == "__main__":
    unittest.main()
