import json
import os
import time

class WebOfTrust:
    """
    Implémentation simplifiée du Web of Trust utilisant le TOFU (Trust On First Use).
    Associe un node_id public (clé Ed25519) à un état de confiance et vérifie s'il y a altération.
    """
    def __init__(self, storage_path: str = ".archipel/trusted_nodes.json"):
        self.storage_path = storage_path
        self._trusted_nodes = {}
        self.load()

    def load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                self._trusted_nodes = json.load(f)

    def save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self._trusted_nodes, f, indent=4)

    def verify_node(self, node_id_hex: str) -> bool:
        """
        Vérifie si un nœud vu pour une reconnexion a la même clé.
        Si la clé publique est inconnue, elle est automatiquement épinglée (TOFU).
        """
        if node_id_hex not in self._trusted_nodes:
            # TOFU: on l'ajoute comme "Pinned"
            self._trusted_nodes[node_id_hex] = {
                "first_seen": time.time(),
                "trusted_score": 1,
            }
            self.save()
            print(f"[WoT] Nouveau Pair: {node_id_hex[:16]}... (Trust On First Use)")
            return True
        else:
            # Le nœud existe. Dans l'absolu, s'il a la même clé publique on valide
            # (ici node_id_hex est la clé publique même, donc c'est implicitement vrai)
            # Mais c'est ici qu'on gérera les révocations et la pénalité de réputation !
            score = self._trusted_nodes[node_id_hex].get("trusted_score", 0)
            if score < 0:
                print(f"[WoT] Alerte: Pair {node_id_hex[:16]}... est bloqué ou révoqué.")
                return False
            return True

    def block_node(self, node_id_hex: str):
        """Révoque et bloque un nœud malveillant."""
        if node_id_hex not in self._trusted_nodes:
            self._trusted_nodes[node_id_hex] = {"first_seen": time.time()}
        
        self._trusted_nodes[node_id_hex]["trusted_score"] = -10
        self.save()
