# Archipel — Spécification du Protocole v1

## Format de Paquet

```
┌─────────────────────────────────────────────────────────┐
│  ARCHIPEL PACKET v1                                     │
├──────────┬──────────┬───────────┬───────────────────────┤
│  MAGIC   │  TYPE    │  NODE_ID  │  PAYLOAD_LEN          │
│  4 bytes │  1 byte  │  32 bytes │  4 bytes (uint32_BE)  │
├──────────┴──────────┴───────────┴───────────────────────┤
│  PAYLOAD (chiffré, longueur variable)                   │
├─────────────────────────────────────────────────────────┤
│  HMAC-SHA256 SIGNATURE  (32 bytes)                      │
└─────────────────────────────────────────────────────────┘
```

### Types de Paquets

| Code   | Nom          | Description                          |
|--------|--------------|--------------------------------------|
| `0x01` | HELLO        | Annonce de présence (UDP Multicast)  |
| `0x02` | PEER_LIST    | Réponse avec liste des nœuds connus  |
| `0x03` | MSG          | Message chiffré E2E                  |
| `0x04` | CHUNK_REQ    | Requête d'un bloc de fichier         |
| `0x05` | CHUNK_DATA   | Transfert d'un bloc de fichier       |
| `0x06` | MANIFEST     | Métadonnées d'un fichier             |
| `0x07` | ACK          | Acquittement                         |
| `0x08` | HELLO_REPLY  | Réponse handshake (clé éphémère)     |
| `0x09` | AUTH         | Authentification (signature)         |
| `0x0A` | AUTH_OK      | Confirmation d'authentification      |

## Handshake Noise-Like

```
Alice                                      Bob
│                                          │
│ ── HELLO (e_A_pub, timestamp) ─────────► │
│                                          │  génère e_B
│ ◄── HELLO_REPLY (e_B_pub, sig_B) ────── │
│                                          │
│  shared = X25519(e_A_priv, e_B_pub)      │
│  session_key = HKDF(shared, 'archipel-v1')
│                                          │
│ ── AUTH (sig_A sur shared_hash) ────────► │
│                                          │  vérifie sig_A
│ ◄── AUTH_OK ──────────────────────────── │
│                                          │
│ ══ Tunnel AES-256-GCM établi ════════════│
```

**Forward Secrecy** : chaque connexion TCP utilise une nouvelle paire de clés éphémères X25519.

## Découverte de Pairs

- **Transport** : UDP Multicast `239.255.42.99:6000`
- **Intervalle HELLO** : 30 secondes
- **Timeout** : 90 secondes sans HELLO = nœud mort
- **Payload HELLO** : `timestamp (uint64_BE, 8 bytes) + tcp_port (uint16_BE, 2 bytes)`

## Transfert de Fichiers

### Manifest
JSON signé contenant : `file_id` (SHA-256 global), `filename`, `size`, `chunk_size` (512 KB), liste des chunks avec index et hash individuel.

### Protocole
1. L'émetteur génère et envoie le **MANIFEST** au récepteur
2. Le récepteur envoie des **CHUNK_REQ** (file_id + chunk_idx)
3. L'émetteur répond avec **CHUNK_DATA** (données + hash)
4. Le récepteur vérifie chaque chunk (SHA-256) puis le fichier global

### Stratégie
- Téléchargement parallèle (3 connexions simultanées)
- Vérification SHA-256 par chunk + vérification globale
- Réessai automatique en cas d'échec (fallback vers autre pair)

## Web of Trust (TOFU)

- **Premier contact** : Trust On First Use — la clé publique est mémorisée
- **Reconnexion** : vérification que la clé correspond à celle mémorisée
- **Révocation** : nœud bloquable via score de confiance négatif
