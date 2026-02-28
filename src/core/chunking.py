import os
import hashlib
import json
import math

CHUNK_SIZE = 512 * 1024  # 512 KB par défaut

class SharedFileIndex:
    """
    Index local des fichiers partagés par ce nœud.
    Mappe file_id (SHA-256 hex) -> filepath sur le disque.
    """
    def __init__(self):
        self._index = {}  # file_id_hex -> { filepath, manifest }
        self._received_manifests = {}  # file_id_hex -> manifest (fichiers proposés par les pairs)

    def register(self, file_id: str, filepath: str, manifest: dict):
        self._index[file_id] = {"filepath": filepath, "manifest": manifest}

    def get_filepath(self, file_id: str) -> str | None:
        entry = self._index.get(file_id)
        return entry["filepath"] if entry else None

    def get_manifest(self, file_id: str) -> dict | None:
        entry = self._index.get(file_id)
        return entry["manifest"] if entry else None

    def add_remote_manifest(self, manifest: dict):
        """Enregistre un manifest reçu d'un pair distant."""
        self._received_manifests[manifest["file_id"]] = manifest

    def get_remote_manifests(self) -> dict:
        return self._received_manifests

    def list_shared_files(self) -> list:
        return [
            {"file_id": fid, "filename": info["manifest"]["filename"], "size": info["manifest"]["size"]}
            for fid, info in self._index.items()
        ]



def canonical_manifest_bytes(manifest: dict) -> bytes:
    base = {k: manifest[k] for k in manifest if k != "signature"}
    return json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")

class FileManager:
    """
    Gère la création de Manifests et la segmentation de fichiers (Chunking).
    """
    def __init__(self, node_identity, file_index: SharedFileIndex):
        self.identity = node_identity
        self.file_index = file_index

    def create_manifest(self, filepath: str) -> dict:
        """
        Génère un MANIFEST pour un fichier, incluant les hashs de tous les chunks.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Le fichier {filepath} n'existe pas.")

        file_size = os.path.getsize(filepath)
        nb_chunks = math.ceil(file_size / CHUNK_SIZE) if file_size > 0 else 0
        
        file_hash_algo = hashlib.sha256()
        chunks_meta = []
        
        with open(filepath, "rb") as f:
            for idx in range(nb_chunks):
                data = f.read(CHUNK_SIZE)
                chunk_hash = hashlib.sha256(data).hexdigest()
                chunks_meta.append({
                    "index": idx,
                    "hash": chunk_hash,
                    "size": len(data)
                })
                file_hash_algo.update(data)
                
        file_id = file_hash_algo.hexdigest()
        
        manifest = {
            "file_id": file_id,
            "filename": os.path.basename(filepath),
            "size": file_size,
            "chunk_size": CHUNK_SIZE,
            "nb_chunks": nb_chunks,
            "chunks": chunks_meta,
            "sender_id": self.identity.public_key_hex,
        }
        
        # Hash et Signature du manifest
        manifest_json_bytes = canonical_manifest_bytes(manifest)
        manifest_hash = hashlib.sha256(manifest_json_bytes).digest()
        signature = self.identity.sign(manifest_hash)
        manifest["signature"] = signature.hex()
        
        # Enregistrer dans l'index local
        self.file_index.register(file_id, os.path.abspath(filepath), manifest)
        print(f"[Chunking] Fichier indexé: {manifest['filename']} | {file_id[:12]}... | {nb_chunks} chunks")
        
        return manifest

    def read_chunk(self, filepath: str, chunk_idx: int) -> bytes:
        """Lit un segment précis du fichier sur le disque."""
        with open(filepath, "rb") as f:
            f.seek(chunk_idx * CHUNK_SIZE)
            return f.read(CHUNK_SIZE)

    def write_chunk(self, dest_path: str, chunk_idx: int, data: bytes):
        """Écrit un chunk récupéré du réseau à la position adéquate."""
        # Créer le fichier vide si nécessaire
        if not os.path.exists(dest_path):
            open(dest_path, 'wb').close()
        with open(dest_path, "r+b") as f:
            f.seek(chunk_idx * CHUNK_SIZE)
            f.write(data)

    def verify_file(self, filepath: str, expected_hash: str) -> bool:
        """Vérifie le SHA-256 global d'un fichier réassemblé."""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                sha.update(data)
        return sha.hexdigest() == expected_hash

    def verify_chunk(self, data: bytes, expected_hash: str) -> bool:
        """Vérifie le SHA-256 d'un chunk individuel."""
        return hashlib.sha256(data).hexdigest() == expected_hash
