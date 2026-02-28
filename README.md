# Archipel 🏝️

**Protocole P2P Chiffré et Décentralisé à Zéro-Connexion**

> Hackathon **"The Geek & The Moon"** — Lomé Business School, Février 2026

Archipel est un réseau local souverain, chiffré bout-en-bout, inspiré de BitTorrent et blindé comme Signal. Chaque nœud est à la fois client et serveur — **aucun serveur central, aucun DNS, aucune CA**.

---

## 🚀 Fonctionnalités

| Feature | Description |
|---------|------------|
| **Découverte P2P** | UDP Multicast automatique sur `239.255.42.99:6000` |
| **Chiffrement E2E** | Handshake Noise-like (X25519 + Ed25519) → tunnel AES-256-GCM |
| **Messagerie sécurisée** | Messages chiffrés, nonce unique par message |
| **Transfert de fichiers** | Chunking 512 KB, SHA-256 par chunk, téléchargement parallèle |
| **Web of Trust (TOFU)** | Authentification sans CA, révocation possible |
| **Assistant IA** | Gemini intégré (optionnel, désactivable `--no-ai`) |

---

## 🏗️ Architecture

```
 ┌────────────────────────────────────────────────────────┐
 │                      CLI INTERACTIF                    │
 │  peers | connect | msg | send | download | status      │
 ├────────────────┬────────────────────┬──────────────────┤
 │ Intégration IA │ Transferts Asynchr │  Messagerie E2E  │
 │   (Gemini)     │  (Chunks + SHA256) │   (AES256-GCM)   │
 ├────────────────┴────────────────────┴──────────────────┤
 │                    ARCHIPEL PROTOCOL v1                │
 │             Packet Parser / Serializer                 │
 ├─────────────────────────────────────┬──────────────────┤
 │ Noise Handshake (Ed25519 / X25519)  │  Web of Trust    │
 ├─────────────────────────────────────┼──────────────────┤
 │         UDP Multicast Discovery     │  TCP E2E Server  │
 │         239.255.42.99:6000          │  Port 7777+      │
 └─────────────────────────────────────┴──────────────────┘
```

**Stack** : Python 3.10+ / asyncio / PyNaCl / cryptography

---

## 📁 Structure du Projet

```
Archipel/
├── main.py                # Point d'entrée principal
├── requirements.txt       # Dépendances Python
├── .env.example           # Template variables d'environnement
├── .gitignore
├── src/
│   ├── crypto/            # PKI (Ed25519), Session (X25519), Encryption (AES-GCM)
│   ├── network/           # Discovery, TCP Server, Connection, Packet, Transfer
│   ├── core/              # Chunking (FileManager), Web of Trust
│   ├── cli/               # Interface REPL interactive
│   └── ai/                # Intégration Gemini (optionnelle)
├── tests/                 # Tests unitaires crypto + chunking
├── docs/                  # Spécification protocole + Architecture
└── demo/                  # Script de démonstration jury
```

---

## 🔧 Installation & Lancement

### 1. Prérequis
- Python 3.10+
- Réseau LAN (même Wi-Fi ou Ethernet)

### 2. Installation
```bash
git clone <repo_url>
cd Archipel
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. (Optionnel) Configurer l'IA
```bash
# Copier le template
cp .env.example .env
# Éditer .env et ajouter votre clé
# Obtenir une clé: https://ai.google.dev

# Ou via variable d'environnement:
# Windows: set GEMINI_API_KEY=votre_clé
# Linux: export GEMINI_API_KEY=votre_clé
```

### 4. Démarrage
```bash
# Nœud 1
python main.py start --port 7777

# Nœud 2 (autre terminal)
python main.py start --port 7778

# Mode offline strict (sans IA)
python main.py start --port 7777 --no-ai
```

---

## 🎮 Guide de Démo — 3 Cas d'Usage

### Cas 1 : Découverte Automatique de Pairs
```bash
# Terminal A
python main.py start --port 7777 --no-ai

# Terminal B
python main.py start --port 7778 --no-ai

# Dans chaque terminal, tapez:
archipel> peers
# → Les 2 nœuds se découvrent en < 60 secondes
```

### Cas 2 : Message Chiffré E2E
```bash
# Terminal A — se connecter à B
archipel> connect 127.0.0.1:7778

# Terminal A — envoyer un message
archipel> msg <node_id_B> Bonjour depuis Archipel !

# Terminal B affiche: 📩 Message de <id>: Bonjour depuis Archipel !
# → Wireshark ne montre que des octets chiffrés
```

### Cas 3 : Transfert de Fichier 50 Mo
```bash
# 1. Préparer le fichier de démo
python demo/demo_scenario.py

# 2. Terminal A — envoyer le fichier
archipel> send <node_id_B> demo/demo_file_50Mo.bin

# 3. Terminal B — voir & télécharger
archipel> receive
archipel> download <file_id>

# → SHA-256 vérifié chunk par chunk + globalement
```

---

## 🔒 Primitives Cryptographiques

| Primitive | Usage | Justification |
|-----------|-------|---------------|
| **Ed25519** | Identité nœud, signatures | Sûr, rapide, clés de 32 bytes, standard moderne |
| **X25519** | ECDH éphémère (Forward Secrecy) | Compatible Ed25519, parfait pour sessions temporaires |
| **AES-256-GCM** | Chiffrement symétrique E2E | AEAD : chiffrement + authentification en un seul algorithme |
| **HKDF-SHA256** | Dérivation de clé de session | Standard NIST, extraction d'entropie fiable |
| **SHA-256** | Intégrité fichiers/chunks | Standard, collision-résistant, omniprésent |

> **Aucun algorithme "maison"** — uniquement des primitives éprouvées via PyNaCl et cryptography.

---

## ⚡ Format de Paquet

```
┌─────────────────────────────────────────────────────────┐
│  MAGIC (4B) │ TYPE (1B) │ NODE_ID (32B) │ LEN (4B)     │
├─────────────┴───────────┴───────────────┴──────────────┤
│  PAYLOAD chiffré (variable)                             │
├─────────────────────────────────────────────────────────┤
│  SIGNATURE Ed25519 (32B)                                │
└─────────────────────────────────────────────────────────┘
```

---

## ⚠️ Limitations Connues

1. **Pas de NAT traversal** — fonctionne uniquement sur LAN local
2. **Rarest First simplifié** — round-robin au lieu de priorité par rareté
3. **Pas de stockage persistant des chunks** — l'index est en mémoire
4. **Single-threaded async** — pas de multi-processing pour les gros transferts
5. **Pas de DHT** — la découverte repose sur le multicast (portée LAN)

### Pistes d'Amélioration
- Implémenter Kademlia DHT pour la découverte hors LAN
- Ajouter un mode Wi-Fi Direct / Bluetooth pour les cas sans AP
- Persistance SQLite de l'index des chunks
- Interface Web locale (React/HTML)

---

## 🧪 Tests

```bash
# Lancer tous les tests
python -m pytest tests/ -v

# Ou individuellement
python -m unittest tests/test_crypto.py
python -m unittest tests/test_chunking.py
```

---

## 🏝️ Commandes CLI

```
╔══════════════════════════════════════════════════════════════╗
║  peers                    Lister les nœuds découverts        ║
║  connect <ip:port>        Se connecter à un pair (Handshake) ║
║  msg <node_id> <texte>    Envoyer un message chiffré E2E     ║
║  send <node_id> <fichier> Envoyer un fichier à un pair       ║
║  receive                  Fichiers disponibles à télécharger ║
║  download <file_id>       Télécharger un fichier             ║
║  status                   État du nœud + stats réseau        ║
║  trust <node_id>          Marquer un pair comme de confiance  ║
║  @archipel-ai <question>  Poser une question à l'IA Gemini   ║
║  help                     Afficher le menu d'aide            ║
║  exit / quit              Arrêter le nœud                    ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 👥 Équipe

| Membre | Rôle | Contributions |
|--------|------|---------------|
| *À compléter* | Lead Dev | Architecture, Crypto, Réseau |
| *À compléter* | Dev | CLI, Tests, Documentation |

---

*Hackathon Archipel 2026 · 24 heures · Construisez quelque chose qui mérite de survivre.*
