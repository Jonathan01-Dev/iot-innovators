"""
Tests unitaires — Chunking et Manifests Archipel
"""
import unittest
import os
import sys
import hashlib
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crypto.pki import NodeIdentity
from src.core.chunking import FileManager, SharedFileIndex, CHUNK_SIZE


class TestSharedFileIndex(unittest.TestCase):
    """Tests pour l'index de fichiers partagés."""
    
    def test_register_and_retrieve(self):
        idx = SharedFileIndex()
        idx.register("abc123", "/path/to/file.txt", {"filename": "file.txt"})
        self.assertEqual(idx.get_filepath("abc123"), "/path/to/file.txt")

    def test_unknown_file_returns_none(self):
        idx = SharedFileIndex()
        self.assertIsNone(idx.get_filepath("nonexistent"))

    def test_remote_manifests(self):
        idx = SharedFileIndex()
        manifest = {"file_id": "xyz789", "filename": "test.pdf", "size": 1024}
        idx.add_remote_manifest(manifest)
        self.assertIn("xyz789", idx.get_remote_manifests())


class TestFileManager(unittest.TestCase):
    """Tests pour la création de manifests et la gestion des chunks."""
    
    def setUp(self):
        self.key_path = ".test_fm_identity.key"
        self.identity = NodeIdentity(self.key_path)
        self.identity.load_or_generate()
        self.file_index = SharedFileIndex()
        self.fm = FileManager(self.identity, self.file_index)

    def tearDown(self):
        if os.path.exists(self.key_path):
            os.remove(self.key_path)

    def test_manifest_creation(self):
        """Vérifie la structure du manifest pour un petit fichier."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Hello Archipel " * 100)
            tmppath = f.name
        
        try:
            manifest = self.fm.create_manifest(tmppath)
            self.assertIn("file_id", manifest)
            self.assertIn("chunks", manifest)
            self.assertIn("signature", manifest)
            self.assertEqual(manifest["nb_chunks"], len(manifest["chunks"]))
            self.assertGreater(manifest["nb_chunks"], 0)
        finally:
            os.unlink(tmppath)

    def test_chunk_read_write(self):
        """Vérifie que les chunks écrits puis relus sont identiques."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            original_data = os.urandom(CHUNK_SIZE * 2 + 100)
            f.write(original_data)
            tmppath = f.name

        try:
            chunk0 = self.fm.read_chunk(tmppath, 0)
            chunk1 = self.fm.read_chunk(tmppath, 1)
            
            self.assertEqual(len(chunk0), CHUNK_SIZE)
            self.assertEqual(chunk0, original_data[:CHUNK_SIZE])
            self.assertEqual(chunk1, original_data[CHUNK_SIZE:CHUNK_SIZE * 2])
        finally:
            os.unlink(tmppath)

    def test_verify_file(self):
        """Vérifie l'intégrité SHA-256 d'un fichier."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            data = b"Test data for hash verification" * 1000
            f.write(data)
            tmppath = f.name
        
        try:
            expected_hash = hashlib.sha256(data).hexdigest()
            self.assertTrue(self.fm.verify_file(tmppath, expected_hash))
            self.assertFalse(self.fm.verify_file(tmppath, "badhash"))
        finally:
            os.unlink(tmppath)

    def test_verify_chunk(self):
        """Vérifie le hash d'un chunk individuel."""
        data = b"Chunk content"
        expected = hashlib.sha256(data).hexdigest()
        self.assertTrue(self.fm.verify_chunk(data, expected))
        self.assertFalse(self.fm.verify_chunk(data, "incorrect"))

    def test_registered_in_index(self):
        """Vérifie que le fichier est enregistré dans l'index après manifest."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Index test " * 50)
            tmppath = f.name
        
        try:
            manifest = self.fm.create_manifest(tmppath)
            path = self.file_index.get_filepath(manifest["file_id"])
            self.assertIsNotNone(path)
        finally:
            os.unlink(tmppath)


if __name__ == "__main__":
    unittest.main()
