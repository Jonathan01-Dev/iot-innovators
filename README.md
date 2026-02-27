# iot-innovators
Archipel Hackathon - Équipe 23
Archipel Architecture

├── Pilier 1: Segmentation des Données (Chunking)
│   ├── Fichiers/messages en blocs (ex. 512 KB)
│   ├── Transfert parallèle
│   ├── Tolérance aux pannes (fallback sur autres pairs)
│   └── Manifest (métadonnées: file_id SHA-256, nb_chunks, hashes par chunk)
├── Pilier 2: Chiffrement de Bout en Bout
│   ├── Paquets chiffrés avant émission (jamais en clair)
│   ├── Primitives: Ed25519 (identité/signature), X25519 (échange clé), AES-256-GCM (chiffrement), HMAC-SHA256 (intégrité)
│   └── Clés éphémères (Forward Secrecy)
├── Couche Réseau P2P
│   ├── Découverte de Pairs (Module 1.1)
│   │   ├── UDP Multicast (239.255.42.99:6000)
│   │   ├── HELLO (toutes 30s)
│   │   ├── PEER_LIST (réponse TCP unicast)
│   │   └── Timeout (90s sans HELLO)
│   ├── Table de Routage (Module 1.2: Peer Table)
│   │   └── Champs: node_id (32 bytes), ip, tcp_port, last_seen, shared_files, reputation
│   └── Serveur TCP (Module 1.3)
│       ├── Port 7777 (configurable)
│       ├── ≥10 connexions parallèles
│       ├── Protocole TLV
│       └── Keep-alive (ping/pong 15s)
├── Chiffrement & Auth (Sprint 2)
│   ├── Handshake (Module 2.2)
│   │   ├── Échange clés X25519
│   │   └── Dérivation session (HKDF-SHA256)
│   └── Web of Trust (Module 2.3: sans CA)
│       ├── TOFU (Trust On First Use)
│       ├── Vérification clé stockée
│       ├── Propagation trust (signatures)
│       └── Révocation (broadcast signé)
├── Chunking & Transfert (Sprint 3)
│   ├── Stratégie Téléchargement (Module 3.2)
│   │   ├── Rarest First
│   │   ├── Parallèle (≥3 connexions)
│   │   └── Vérification SHA-256 par chunk
│   ├── Protocole Transfert (Module 3.3)
│   │   ├── CHUNK_REQ (file_id, chunk_idx)
│   │   ├── CHUNK_DATA (data chiffrée, hash)
│   │   └── ACK (status: OK, MISMATCH, NOT_FOUND)
│   └── Stockage & Réplication (Module 3.4)
│       ├── Index local (.archipel/index.db)
│       ├── Partage automatique
│       └── Replication factor configurable
├── Intégration (Sprint 4)
│   ├── Interface (Module 4.1: CLI ou UI)
│   │   └── Commandes: start, peers, msg, send, receive, download, status, trust
│   └── Gemini API (Module 4.2: isolée, offline fallback)
│       ├── Déclenchement: @archipel-ai ou /ask
│       └── Contexte: derniers messages
├── Format Paquet (V1)
│   ├── MAGIC (4 bytes)
│   ├── TYPE (1 byte: HELLO, MSG, etc.)
│   ├── NODE-ID (32 bytes)
│   ├── PAYLOAD_LEN (4 bytes)
│   ├── PAYLOAD (chiffré)
│   └── SIGNATURE (HMAC-SHA256 32 bytes)
└── Transport Local (Recommandé)
    ├── UDP Multicast (découverte)
    └── TCP Sockets (transfert)
