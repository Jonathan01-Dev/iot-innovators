"""
Archipel — Script de Démo pour le Jury
Usage: python demo/demo_scenario.py

Ce script crée un fichier de test et affiche les instructions
pour démontrer les 3 cas d'usage d'Archipel.
"""
import os
import hashlib
import sys

DEMO_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo
DEMO_FILE = "demo/demo_file_50Mo.bin"


def create_demo_file():
    """Crée un fichier de test de 50 Mo avec du contenu pseudo-aléatoire reproductible."""
    if os.path.exists(DEMO_FILE):
        print(f"  ✅ Fichier de démo déjà existant: {DEMO_FILE}")
    else:
        print(f"  📦 Création du fichier de démo ({DEMO_FILE_SIZE // (1024 * 1024)} Mo)...")
        os.makedirs("demo", exist_ok=True)
        # Contenu reproductible (pas besoin de random pour la démo)
        chunk = b"ARCHIPEL_DEMO_2026_LBS_HACKATHON_" * 1000  # ~33 KB
        with open(DEMO_FILE, "wb") as f:
            written = 0
            while written < DEMO_FILE_SIZE:
                to_write = min(len(chunk), DEMO_FILE_SIZE - written)
                f.write(chunk[:to_write])
                written += to_write
    
    # Afficher le hash
    sha = hashlib.sha256()
    with open(DEMO_FILE, "rb") as f:
        while True:
            data = f.read(512 * 1024)
            if not data:
                break
            sha.update(data)
    print(f"  🔑 SHA-256: {sha.hexdigest()}")
    print(f"  📂 Taille : {os.path.getsize(DEMO_FILE) / 1024 / 1024:.1f} Mo\n")


def print_scenario():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              ARCHIPEL — SCÉNARIO DE DÉMO JURY               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  PRÉ-REQUIS: 2 terminaux côte à côte                       ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ÉTAPE 1: DÉMARRAGE DES NŒUDS                              ║
║                                                              ║
║  Terminal A:                                                 ║
║    python main.py start --port 7777 --no-ai                 ║
║                                                              ║
║  Terminal B:                                                 ║
║    python main.py start --port 7778 --no-ai                 ║
║                                                              ║
║  → Observez la découverte automatique (UDP Multicast)       ║
║  → Tapez "peers" dans chaque terminal                       ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ÉTAPE 2: CONNEXION E2E + MESSAGE CHIFFRÉ                  ║
║                                                              ║
║  Terminal A:                                                 ║
║    archipel> connect 127.0.0.1:7778                         ║
║    archipel> msg <node_id_B> Bonjour depuis Archipel !      ║
║                                                              ║
║  → Terminal B affiche le message déchiffré                   ║
║  → Sur Wireshark: uniquement des octets chiffrés !          ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ÉTAPE 3: TRANSFERT DE FICHIER 50 Mo                        ║
║                                                              ║
║  Terminal A:                                                 ║
║    archipel> send <node_id_B> demo/demo_file_50Mo.bin       ║
║                                                              ║
║  Terminal B:                                                 ║
║    archipel> receive                                         ║
║    archipel> download <file_id>                             ║
║                                                              ║
║  → Observez: chunks téléchargés, SHA-256 vérifié            ║
║  → Fichier identique à la source !                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    print("\n  🏝️  ARCHIPEL — Préparation de la démo\n")
    create_demo_file()
    print_scenario()
