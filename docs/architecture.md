# Archipel — Architecture

## Vue d'ensemble

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

## Modules

```
src/
├── ai/
│   └── gemini.py          # Intégration Gemini (optionnelle, désactivable)
├── cli/
│   └── repl.py            # Interface interactive (REPL) avec toutes les commandes
├── core/
│   ├── chunking.py        # FileManager, SharedFileIndex, manifest, chunks
│   └── wot.py             # Web of Trust (TOFU), révocation
├── crypto/
│   ├── encryption.py      # SecureChannel (AES-256-GCM)
│   ├── pki.py             # NodeIdentity (Ed25519 signing/verification)
│   └── session.py         # SecureSession (X25519 ECDH + HKDF)
└── network/
    ├── connection.py       # ArchipelConnection (handshake + messages E2E)
    ├── discovery.py        # UDP Multicast HELLO loop
    ├── packet.py           # ArchipelPacket (serialization/parsing binaire)
    ├── peer_table.py       # PeerTable (gestion des pairs en mémoire)
    ├── tcp_server.py       # TCPServer asyncio
    └── transfer.py         # TransferManager (envoi/réception fichiers)
```

## Flux de données

1. **Découverte** : `UDP Multicast HELLO → PeerTable.upsert()`
2. **Connexion** : `CLI connect → TCP → Handshake (X25519 + Ed25519) → SecureChannel`
3. **Message** : `CLI msg → SecureChannel.encrypt → TCP send → SecureChannel.decrypt`
4. **Fichier** : `CLI send → Manifest → CHUNK_REQ/CHUNK_DATA → SHA-256 verify → Assemble`

## Primitives Cryptographiques

| Primitive    | Usage                                 | Bibliothèque          |
|-------------|---------------------------------------|-----------------------|
| Ed25519     | Identité nœud, signatures             | PyNaCl (SigningKey)   |
| X25519      | Échange de clé Diffie-Hellman éphémère | cryptography.hazmat   |
| AES-256-GCM | Chiffrement symétrique E2E            | cryptography (AESGCM) |
| HKDF-SHA256 | Dérivation de clé de session          | cryptography (HKDF)   |
| SHA-256     | Intégrité fichiers et chunks          | hashlib               |
