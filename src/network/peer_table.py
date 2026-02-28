import time

class PeerTable:
    def __init__(self):
        # Dictionnaire: clé = node_id (bytes), valeur = dict d'informations
        self.peers = {}
        self.PEER_TIMEOUT = 90  # nœud considéré mort après 90 secondes sans HELLO

    def update_peer(self, node_id: bytes, ip: str, tcp_port: int) -> bool:
        """
        Met à jour ou insère un pair.
        Retourne True s'il s'agit d'un nouveau pair, False si c'est une simple mise à jour.
        """
        now = time.time()
        is_new = node_id not in self.peers
        
        if is_new:
            self.peers[node_id] = {
                "node_id": node_id,
                "ip": ip,
                "tcp_port": tcp_port,
                "last_seen": now,
                "shared_files": [],
                "reputation": 1.0  # par défaut
            }
        else:
            self.peers[node_id]["ip"] = ip
            self.peers[node_id]["tcp_port"] = tcp_port
            self.peers[node_id]["last_seen"] = now
            
        return is_new

    def get_active_peers(self) -> list:
        """Retourne la liste des pairs qui ont émis un HELLO récemment."""
        now = time.time()
        active = []
        for _id, data in list(self.peers.items()):
            if now - data["last_seen"] > self.PEER_TIMEOUT:
                # Retirer silencieusement le pair mort
                del self.peers[_id]
            else:
                active.append(data)
        return active
        
    def get_peer(self, node_id: bytes) -> dict:
        """Récupère un pair spécifique."""
        self.get_active_peers() # Trigger le nettoyage
        return self.peers.get(node_id)
