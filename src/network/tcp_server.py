import asyncio
from src.network.connection import ArchipelConnection
from src.core.wot import WebOfTrust

class TCPServer:
    def __init__(self, node_identity, port: int, peer_table, wot: WebOfTrust):
        self.identity = node_identity
        self.port = port
        self.peer_table = peer_table
        self.wot = wot
        self.server = None
        self.active_connections = {}  # node_id -> ArchipelConnection
        self.transfer_manager = None

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[TCP] Nouvelle connexion entrante de {addr}")
        
        # Envelopper dans notre gestionnaire de connexion sécurisée
        conn = ArchipelConnection(reader, writer, self.identity, self.wot)
        try:
            # Effectuer le handshake en tant que Serveur (Bob)
            await conn.do_server_handshake()
            
            # L'ajouter aux connexions actives (clé = node_id hex)
            node_id_hex = conn.peer_node_id.hex()
            self.active_connections[node_id_hex] = conn
            
            # Boucle d'écoute des messages chiffrés E2E
            while True:
                plaintext = await conn.receive_encrypted_message()
                
                # Essayer de décoder comme du JSON pour le protocole de transfert
                try:
                    import json
                    req = json.loads(plaintext.decode('utf-8'))
                    if "action" in req and self.transfer_manager:
                        await self.transfer_manager.handle_incoming_request(conn, plaintext)
                        continue
                except:
                    pass
                
                print(f"📩 Message de {node_id_hex[:8]}: {plaintext.decode('utf-8', errors='replace')}")

        except asyncio.IncompleteReadError:
            pass # Le pair a fermé la connexion propement
        except Exception as e:
            print(f"[TCP] Erreur avec le pair {addr}: {str(e)}")
        finally:
            writer.close()
            await writer.wait_closed()
            if conn.peer_node_id:
               self.active_connections.pop(conn.peer_node_id.hex(), None)
            print(f"[TCP] Déconnecté de {addr}")

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, '0.0.0.0', self.port
        )
        print(f"[TCP] Protocole E2E en écoute sur le port {self.port} 🔒")
        
    def stop(self):
        if self.server:
            self.server.close()
