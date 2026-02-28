import argparse
import sys
import asyncio
import os
from pathlib import Path
from src.crypto.pki import NodeIdentity
from src.network.peer_table import PeerTable
from src.network.discovery import DiscoveryProtocol, create_multicast_socket
from src.network.tcp_server import TCPServer
from src.core.wot import WebOfTrust
from src.core.chunking import FileManager, SharedFileIndex
from src.network.transfer import TransferManager
from src.ai.gemini import ArchipelAI
from src.cli.repl import ArchipelCLI

BANNER = r"""
    ___              __    _            __
   /   |  __________/ /_  (_)___  ___  / /
  / /| | / ___/ ___/ __ \/ / __ \/ _ \/ / 
 / ___ |/ /  / /__/ / / / / /_/ /  __/ /  
/_/  |_/_/   \___/_/ /_/_/ .___/\___/_/   
                        /_/               
  P2P Chiffré & Décentralisé — v1.0
  Hackathon LBS · Février 2026
"""

async def start_node(port: int, identity: NodeIdentity, wot: WebOfTrust):
    table = PeerTable()
    file_index = SharedFileIndex()
    
    # 1. Démarrer le serveur TCP
    tcp_server = TCPServer(identity, port, table, wot)
    await tcp_server.start()

    # 2. Démarrer la découverte Multicast UDP
    loop = asyncio.get_running_loop()
    sock = create_multicast_socket()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DiscoveryProtocol(identity, port, table),
        sock=sock
    )
    
    # 3. Initialiser le gestionnaire de transfert
    file_manager = FileManager(identity, file_index)
    transfer_manager = TransferManager(tcp_server, file_manager, file_index)
    
    # 4. Initialiser l'IA
    ai_assistant = ArchipelAI()
    
    # 5. Démarrer le CLI Interactif (REPL)
    cli = ArchipelCLI(tcp_server, table, wot, identity, ai_assistant, transfer_manager)
    asyncio.create_task(cli.start_repl())
    
    print(BANNER)
    print(f"  🔑 Node ID : {identity.public_key_hex}")
    print(f"  📡 UDP     : Multicast 239.255.42.99:6000")
    print(f"  🔒 TCP E2E : 0.0.0.0:{port}")
    print(f"  🤖 Gemini  : {'Actif' if ai_assistant.is_active else 'Désactivé'}")
    print(f"  {'─' * 50}\n")
    
    # Garder la boucle active
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n  Arrêt du nœud Archipel...")
        tcp_server.stop()
        transport.close()

def main():
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

    env_path = Path(__file__).resolve().parents[0] / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip().lstrip("\ufeff")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)

    parser = argparse.ArgumentParser(
        description="Archipel — Protocole P2P Chiffré et Décentralisé à Zéro-Connexion"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Commande 'start'
    start_parser = subparsers.add_parser("start", help="Démarre le nœud Archipel")
    start_parser.add_argument("--port", type=int, default=7777, help="Port TCP d'écoute (défaut: 7777)")

    # Commande 'status'
    subparsers.add_parser("status", help="Affiche l'état du nœud (hors-ligne)")

    args = parser.parse_args()

    port = getattr(args, 'port', 7777)
    no_ai = False
    key_path = f".archipel_{port}/identity.key"
    wot_path = f".archipel_{port}/trusted_nodes.json"
    
    identity = NodeIdentity(key_path)
    identity.load_or_generate()
    
    wot = WebOfTrust(wot_path)

    if args.command == "start":
        try:
            asyncio.run(start_node(port, identity, wot))
        except KeyboardInterrupt:
            pass
            
    elif args.command == "status":
        print(f"  🔑 Node ID: {identity.public_key_hex}")
        print(f"  📡 Statut : Hors ligne (utilisez 'start' pour démarrer)")
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
