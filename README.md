Archipel
========

Archipel est un outil pour partager des fichiers et des messages en local, sans passer par un serveur central. Chaque poste trouve les autres sur le réseau (multicast), sécurise ses échanges (AES‑256-GCM, signatures Ed25519) et permet de transférer des fichiers qui dépassent 50 Mo.

Principales actions
-------------------

- `python main.py start --port N` : démarre un nœud Archipel sur le port TCP `N`.
- Dans le REPL (`archipel> …`), les commandes utiles :
  - `peers` : liste les nœuds que tu vois.
  - `connect <ip:port>` puis `msg <id> <texte>` : envoie un message chiffré.
  - `send <node_id> <chemin_du_fichier>` : envoie un fichier depuis ton disque.
  - `receive` puis `download <file_id>` : récupère un fichier qu’un pair a listé.
  - `trust <node_id>` : marque un pair de confiance.
  - `@archipel-ai <question>` : l’assistant Gemini répond (optionnel si tu as `GEMINI_API_KEY`).

Commandes libres
-----------------

- Le dossier `demo/` contient un script qui prépare un fichier de 50 Mo (utilise `python demo/demo_scenario.py`).
- Tu peux partager ce fichier en pointant `send` vers n’importe quel chemin de ton PC, Archipel le lit et découpe en chunks.
- Le fichier `.env` livré contient déjà `GEMINI_API_KEY`, donc l’assistant Gemini se lance automatiquement (sans `--no-ai`).

Tests
-----

- `python -m pytest -q` vérifie la crypto, le chunking et le handshake.

Déploiement rapide
------------------

1. `python -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `python main.py start --port 7777` (un terminal)  
   `python main.py start --port 7778` (un autre terminal)  
   puis `archipel>` pour lancer `peers`, `connect`, `send`, etc.

Notes
-----

- Aucune dépendance externe n’est nécessaire pour la découverte (tout reste en LAN).
- Tous les fichiers llevan en mémoire, et les manifest sont signés pour vérifier qu’on n’a pas été trompé.
