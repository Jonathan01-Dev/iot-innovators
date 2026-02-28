import asyncio
import sys
import os
from src.network.connection import ArchipelConnection
from src.core.wot import WebOfTrust

HELP_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║                 ARCHIPEL — Commandes CLI                     ║
╠══════════════════════════════════════════════════════════════╣
║  peers                    Lister les nœuds découverts        ║
║  connect <ip:port>        Se connecter à un pair (Handshake) ║
║  msg <node_id> <texte>    Envoyer un message chiffré E2E     ║
║  send <node_id> <fichier> Envoyer un fichier à un pair       ║
║  receive                  Fichiers disponibles à télécharger ║
║  download <file_id>       Télécharger un fichier             ║
║  status                   État du nœud + stats réseau        ║
║  trust <node_id>          Marquer un pair comme de confiance  ║
║  @archipel-ai <question>  Poser une question à l'IA Gemini   ║
║  help                     Afficher ce menu                   ║
║  exit / quit              Arrêter le nœud                    ║
╚══════════════════════════════════════════════════════════════╝
"""


class ArchipelCLI:
    """
    Interface Ligne de Commande Interactive (REPL) pour le nœud Archipel.
    """
    def __init__(self, tcp_server, peer_table, wot, identity, ai_assistant, transfer_manager=None):
        self.tcp_server = tcp_server
        self.peer_table = peer_table
        self.wot = wot
        self.identity = identity
        self.ai = ai_assistant
        self.transfer = transfer_manager

    async def start_repl(self):
        """Boucle REPL asynchrone lisant sur sys.stdin."""
        print(HELP_TEXT)
        
        try:
            import aioconsole
        except ImportError:
            print("❌ Erreur: Le module 'aioconsole' est manquant. Installez-le avec 'pip install aioconsole'.")
            sys.exit(1)
            
        while True:
            try:
                line = await aioconsole.ainput("archipel> ")
            except EOFError:
                break
                
            line = line.strip()
            if not line:
                continue
                
            args = line.split()
            cmd = args[0].lower()
            
            try:
                if line.startswith("@archipel-ai"):
                    await self._cmd_ai(line)
                elif cmd == "help":
                    print(HELP_TEXT)
                elif cmd == "peers":
                    self._cmd_peers()
                elif cmd == "connect" and len(args) >= 2:
                    await self._cmd_connect(args[1])
                elif cmd == "msg" and len(args) >= 3:
                    await self._cmd_msg(args[1], " ".join(args[2:]))
                elif cmd == "send" and len(args) >= 3:
                    await self._cmd_send(args[1], " ".join(args[2:]))
                elif cmd == "receive":
                    self._cmd_receive()
                elif cmd == "download" and len(args) >= 2:
                    await self._cmd_download(args[1])
                elif cmd == "status":
                    self._cmd_status()
                elif cmd == "trust" and len(args) == 2:
                    self._cmd_trust(args[1])
                elif cmd in ["exit", "quit"]:
                    print("Arrêt du nœud...")
                    sys.exit(0)
                else:
                    print("❓ Commande inconnue. Tapez 'help' pour la liste des commandes.")
            except Exception as e:
                print(f"❌ Erreur: {e}")

    def _cmd_peers(self):
        peers = self.peer_table.get_active_peers()
        if not peers:
            print("  Aucun pair découvert sur le réseau.")
            return
        print(f"\n  {'NODE ID':<20} {'ADRESSE':<22} {'CONFIANCE':<12} {'E2E'}")
        print(f"  {'─' * 70}")
        for p in peers:
            nid = p["node_id"].hex()
            nid_short = nid[:16] + "..."
            addr = f"{p['ip']}:{p['tcp_port']}"
            trust_status = "✅ TOFU" if self.wot.verify_node(nid) else "⚠️ Inconnu"
            e2e = "🔒 Actif" if nid in self.tcp_server.active_connections else "—"
            print(f"  {nid_short:<20} {addr:<22} {trust_status:<12} {e2e}")
        print()

    async def _cmd_connect(self, addr: str):
        """Initie une connexion et un handshake E2E vers un pair."""
        # Nettoyer l'adresse (au cas où l'utilisateur tape des < >, ( ) ou guillemets)
        addr = addr.strip("<>()'\"")
        
        if ":" not in addr:
            print("  Usage: connect <ip:port>  (ex: connect 192.168.1.10:7777)")
            return

        ip, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            print(f"  ❌ Port invalide : {port_str}")
            return

        print(f"  🔗 Connexion vers {ip}:{port}...")
        conn = ArchipelConnection(None, None, self.identity, self.wot)
        
        try:
            print("  [DEBUG] Appel de connect_and_do_client_handshake()...")
            # Use wait_for to prevent indefinite hangs
            await asyncio.wait_for(conn.connect_and_do_client_handshake(ip, port), timeout=10.0)
            print("  [DEBUG] Handshake terminé avec succès.")
        except asyncio.TimeoutError:
            print("  ❌ [DEBUG] Timeout du handshake (10s) !")
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ Erreur de connexion : {e}")
            return

        # Enregistrer la connexion active
        node_id_hex = conn.peer_node_id.hex()
        self.tcp_server.active_connections[node_id_hex] = conn
        print(f"  ✅ Tunnel E2E établi avec {node_id_hex[:16]}...")

        # Démarrer l'écoute des messages depuis ce pair
        asyncio.create_task(self._listen_to_peer(conn))

    async def _listen_to_peer(self, conn):
        """Écoute les messages entrants d'un pair connecté en tant que client."""
        node_id_hex = conn.peer_node_id.hex()
        try:
            while True:
                plaintext = await conn.receive_encrypted_message()
                # Vérifier si c'est un message de protocole (transfert)
                try:
                    import json
                    req = json.loads(plaintext.decode('utf-8'))
                    if "action" in req and self.transfer:
                        await self.transfer.handle_incoming_request(conn, plaintext)
                        continue
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                print(f"\n📩 Message de {node_id_hex[:8]}: {plaintext.decode('utf-8', errors='replace')}")
                print("archipel> ", end="", flush=True)
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            pass
        finally:
            self.tcp_server.active_connections.pop(node_id_hex, None)

    async def _cmd_msg(self, target_id: str, text: str):
        conn = self._find_connection(target_id)
        if conn:
            await conn.send_encrypted_message(text.encode('utf-8'))
            print(f"  📨 Message chiffré envoyé !")
        else:
            print(f"  ❌ Pair non connecté. Utilisez 'connect <ip:port>' d'abord.")

    async def _cmd_send(self, target_id: str, filepath: str):
        """Envoyer un fichier à un pair connecté."""
        if not self.transfer:
            print("  ❌ TransferManager non initialisé.")
            return

        if not os.path.exists(filepath):
            print(f"  ❌ Fichier introuvable: {filepath}")
            return

        conn = self._find_connection(target_id)
        if not conn:
            print(f"  ❌ Pair non connecté. Utilisez 'connect <ip:port>' d'abord.")
            return

        # 1. Générer le manifest
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        print(f"  📦 Préparation de '{os.path.basename(filepath)}' ({size_mb:.1f} Mo)...")
        manifest = self.transfer.file_manager.create_manifest(filepath)

        # 2. Envoyer le manifest au pair
        peer_id = conn.peer_node_id.hex()
        await self.transfer.send_manifest(manifest, peer_id)
        print(f"  ✅ Manifest envoyé ! Le pair peut maintenant télécharger le fichier.")
        print(f"     File ID: {manifest['file_id'][:16]}...")

    def _cmd_receive(self):
        """Affiche les fichiers disponibles au téléchargement (manifests reçus)."""
        if not self.transfer:
            print("  ❌ TransferManager non initialisé.")
            return

        manifests = self.transfer.file_index.get_remote_manifests()
        if not manifests:
            print("  Aucun fichier disponible. Attendez qu'un pair vous envoie un manifest.")
            return

        print(f"\n  {'FICHIER':<30} {'TAILLE':<12} {'CHUNKS':<10} {'FILE ID'}")
        print(f"  {'─' * 75}")
        for fid, m in manifests.items():
            size = f"{m['size'] / 1024 / 1024:.1f} Mo"
            print(f"  {m['filename']:<30} {size:<12} {m['nb_chunks']:<10} {fid[:16]}...")
        print(f"\n  Utilisez: download <file_id_partiel> pour télécharger.\n")

    async def _cmd_download(self, file_id_partial: str):
        """Télécharge un fichier depuis un manifest reçu."""
        if not self.transfer:
            print("  ❌ TransferManager non initialisé.")
            return

        manifests = self.transfer.file_index.get_remote_manifests()
        manifest = None
        for fid, m in manifests.items():
            if fid.startswith(file_id_partial):
                manifest = m
                break

        if not manifest:
            print(f"  ❌ Fichier non trouvé. Utilisez 'receive' pour voir les fichiers disponibles.")
            return

        await self.transfer.download_file(manifest)

    def _cmd_status(self):
        peers = self.peer_table.get_active_peers()
        e2e = len(self.tcp_server.active_connections)
        shared = self.transfer.file_index.list_shared_files() if self.transfer else []

        print(f"\n  ╔════════════════════════════════════════╗")
        print(f"  ║         ARCHIPEL — État du nœud         ║")
        print(f"  ╠════════════════════════════════════════╣")
        print(f"  ║  🔑 ID    : {self.identity.public_key_hex[:24]}...  ║")
        print(f"  ║  📡 Pairs : {len(peers)} découverts, {e2e} tunnels E2E  ║")
        print(f"  ║  📂 Shared: {len(shared)} fichier(s)                  ║")
        print(f"  ╚════════════════════════════════════════╝\n")

        if shared:
            for sf in shared:
                print(f"    📄 {sf['filename']} ({sf['size'] / 1024 / 1024:.1f} Mo) — {sf['file_id'][:12]}...")

    def _cmd_trust(self, node_id_partial: str):
        # Recherche du node_id complet
        for p in self.peer_table.get_active_peers():
            nid = p["node_id"].hex()
            if nid.startswith(node_id_partial):
                self.wot.verify_node(nid)  # TOFU l'ajoutera s'il n'existe pas
                print(f"  ✅ {nid[:16]}... marqué comme de confiance.")
                return
        print(f"  ❌ Pair non trouvé dans la table des pairs.")

    async def _cmd_ai(self, line: str):
        query = line.replace("@archipel-ai", "").strip()
        if not query:
            print("  Usage: @archipel-ai <votre question>")
            return
        peers = self.peer_table.get_active_peers()
        context = (
            f"Node ID: {self.identity.public_key_hex[:16]}\n"
            f"Pairs actifs: {len(peers)}\n"
            f"Sessions E2E: {len(self.tcp_server.active_connections)}"
        )
        print("  🤖 Interrogation de Gemini...")
        answer = self.ai.ask(query, context)
        print(f"  🤖 {answer}")

    def _find_connection(self, partial_id: str):
        """Cherche une connexion active par ID partiel."""
        for full_id, conn in self.tcp_server.active_connections.items():
            if full_id.startswith(partial_id):
                return conn
        return None
