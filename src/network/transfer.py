import asyncio
import hashlib
import json
import os
import base64
from src.crypto.pki import NodeIdentity
from src.network.packet import ArchipelPacket, PacketType
from src.core.chunking import FileManager, SharedFileIndex, canonical_manifest_bytes

DOWNLOAD_DIR = ".archipel_downloads"


class TransferManager:
    """
    Gestion des transferts de fichiers réels sur les canaux chiffrés E2E.
    Supporte: envoi de manifest, requête/réponse de chunks, téléchargement parallèle,
    vérification SHA-256 par chunk et globale.
    """
    def __init__(self, tcp_server, file_manager: FileManager, file_index: SharedFileIndex):
        self.tcp_server = tcp_server
        self.file_manager = file_manager
        self.file_index = file_index

        # Enregistre ce gestionnaire pour traiter les requêtes entrantes
        self.tcp_server.transfer_manager = self

        # Futures pour la réception asynchrone des chunks
        self._chunk_futures = {}  # (file_id, chunk_idx) -> asyncio.Future

        # Créer le dossier de téléchargement
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    async def send_manifest(self, manifest: dict, peer_id_hex: str):
        """Envoie un manifest à un pair connecté."""
        conn = self.tcp_server.active_connections.get(peer_id_hex)
        if not conn:
            raise Exception(f"Pas de connexion active avec {peer_id_hex[:8]}...")

        msg = json.dumps({
            "action": "manifest",
            "manifest": manifest
        }).encode()

        await conn.send_encrypted_message(msg)
        print(f"📋 Manifest envoyé à {peer_id_hex[:8]} pour '{manifest['filename']}'")

    async def download_file(self, manifest: dict, dest_dir: str = DOWNLOAD_DIR):
        """
        Télécharge le fichier complet en demandant les chunks aux pairs connectés.
        Vérification SHA-256 par chunk + vérification globale à la fin.
        """
        file_id = manifest["file_id"]
        total_chunks = manifest["nb_chunks"]
        filename = manifest["filename"]
        dest_path = os.path.join(dest_dir, filename)

        # Pré-allouer le fichier
        with open(dest_path, "wb") as f:
            f.seek(manifest["size"] - 1)
            f.write(b'\0')

        print(f"📥 Téléchargement de '{filename}' ({total_chunks} chunks, {manifest['size'] / 1024 / 1024:.1f} Mo)")

        active_peers = list(self.tcp_server.active_connections.keys())
        if not active_peers:
            raise Exception("Aucun pair connecté pour télécharger.")

        failed_chunks = []
        success_count = 0

        # Télécharger par lots (parallélisme limité à 3 connexions)
        semaphore = asyncio.Semaphore(3)

        async def fetch_chunk(chunk_meta: dict, peer_idx: int):
            nonlocal success_count
            async with semaphore:
                chunk_idx = chunk_meta["index"]
                expected_hash = chunk_meta["hash"]
                peer_id = active_peers[peer_idx % len(active_peers)]
                conn = self.tcp_server.active_connections.get(peer_id)

                if not conn:
                    failed_chunks.append(chunk_idx)
                    return

                # Créer un Future pour attendre la réponse
                future_key = (file_id, chunk_idx)
                loop = asyncio.get_running_loop()
                self._chunk_futures[future_key] = loop.create_future()

                # Envoyer la requête
                req_data = json.dumps({
                    "action": "req_chunk",
                    "file_id": file_id,
                    "chunk_idx": chunk_idx
                }).encode()

                await conn.send_encrypted_message(req_data)

                try:
                    # Attendre la réponse (timeout 30s)
                    chunk_data = await asyncio.wait_for(self._chunk_futures[future_key], timeout=30)

                    # Vérifier le hash du chunk
                    if self.file_manager.verify_chunk(chunk_data, expected_hash):
                        self.file_manager.write_chunk(dest_path, chunk_idx, chunk_data)
                        success_count += 1
                        # Barre de progression
                        pct = int(success_count / total_chunks * 100)
                        print(f"\r  ⬇️  [{pct:3d}%] {success_count}/{total_chunks} chunks", end="", flush=True)
                    else:
                        print(f"\n  ⚠️  Chunk {chunk_idx}: HASH_MISMATCH — re-téléchargement nécessaire")
                        failed_chunks.append(chunk_idx)

                except asyncio.TimeoutError:
                    print(f"\n  ⏱  Chunk {chunk_idx}: timeout — on réessaiera")
                    failed_chunks.append(chunk_idx)
                finally:
                    self._chunk_futures.pop(future_key, None)

        tasks = [fetch_chunk(cm, i) for i, cm in enumerate(manifest["chunks"])]
        await asyncio.gather(*tasks)
        print()  # Retour à la ligne

        # Retry sur chunks échoués (fallback vers un autre pair)
        if failed_chunks:
            print(f"  🔄 Re-téléchargement de {len(failed_chunks)} chunk(s) échoués...")
            for retry_idx in failed_chunks:
                chunk_meta = manifest["chunks"][retry_idx]
                await fetch_chunk(chunk_meta, retry_idx + 1)

        # Vérification finale SHA-256
        if self.file_manager.verify_file(dest_path, file_id):
            print(f"✅ Fichier '{filename}' téléchargé et vérifié ! SHA-256 OK")
            print(f"   📂 Sauvegardé dans: {os.path.abspath(dest_path)}")
            # Enregistrer dans l'index local (on devient seed)
            self.file_index.register(file_id, os.path.abspath(dest_path), manifest)
        else:
            print(f"❌ ERREUR: SHA-256 global ne correspond pas ! Fichier corrompu.")

    async def handle_incoming_request(self, conn, plaintext: bytes):
        """Appelé par TCPServer lorsqu'il reçoit un MSG contenant du JSON protocole."""
        try:
            req = json.loads(plaintext.decode())
            action = req.get("action")

            if action == "req_chunk":
                await self._handle_chunk_request(conn, req)

            elif action == "chunk_data":
                self._handle_chunk_response(req)

            elif action == "manifest":
                self._handle_manifest(req, conn)

        except json.JSONDecodeError:
            pass

    async def _handle_chunk_request(self, conn, req: dict):
        """Sert un chunk depuis le disque local."""
        file_id = req["file_id"]
        chunk_idx = req["chunk_idx"]

        filepath = self.file_index.get_filepath(file_id)
        if not filepath or not os.path.exists(filepath):
            # Fichier non disponible => envoyer NOT_FOUND
            res = json.dumps({
                "action": "chunk_data",
                "file_id": file_id,
                "chunk_idx": chunk_idx,
                "error": "NOT_FOUND"
            }).encode()
            await conn.send_encrypted_message(res)
            return

        # Lire le chunk réel
        chunk_data = self.file_manager.read_chunk(filepath, chunk_idx)
        chunk_hash = hashlib.sha256(chunk_data).hexdigest()

        # Encoder en base64 pour le transport JSON
        res = json.dumps({
            "action": "chunk_data",
            "file_id": file_id,
            "chunk_idx": chunk_idx,
            "data_b64": base64.b64encode(chunk_data).decode('ascii'),
            "chunk_hash": chunk_hash
        }).encode()

        await conn.send_encrypted_message(res)

    def _handle_chunk_response(self, req: dict):
        """Résout le Future associé à un chunk reçu."""
        file_id = req["file_id"]
        chunk_idx = req["chunk_idx"]
        future_key = (file_id, chunk_idx)

        if "error" in req:
            future = self._chunk_futures.get(future_key)
            if future and not future.done():
                future.set_exception(Exception(req["error"]))
            return

        chunk_data = base64.b64decode(req["data_b64"])
        future = self._chunk_futures.get(future_key)
        if future and not future.done():
            future.set_result(chunk_data)

    def _handle_manifest(self, req: dict, conn) -> None:
        """Enregistre un manifest reçu d'un pair, après vérification crypto."""
        manifest = req.get("manifest", {})
        sig_hex = manifest.get("signature", "")
        if not sig_hex:
            print("[Transfer] Manifest sans signature ignoré.")
            return
        try:
            signature = bytes.fromhex(sig_hex)
        except ValueError:
            print("[Transfer] Signature du manifest invalide (hex).")
            return
        if not NodeIdentity.verify(conn.peer_node_id, canonical_manifest_bytes(manifest), signature):
            print("[Transfer] Signature du manifest invalide (vérification Ed25519).")
            return
        self.file_index.add_remote_manifest(manifest)
        size_mb = manifest["size"] / 1024 / 1024
        print(f"\n📋 Nouveau fichier disponible: '{manifest['filename']}' ({size_mb:.1f} Mo) — ID: {manifest['file_id'][:12]}...")
        print(f"   Tapez: download {manifest['file_id'][:12]}")
        print("archipel> ", end="", flush=True)
