import asyncio
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.network.connection import ArchipelConnection
from src.network.tcp_server import TCPServer
from src.crypto.pki import NodeIdentity
from src.core.wot import WebOfTrust
import tempfile

async def main():
    # Setup Node 1 (Server)
    id1_path = os.path.join(tempfile.gettempdir(), "n1.key")
    id1 = NodeIdentity(id1_path)
    id1.load_or_generate()
    
    wot1_path = os.path.join(tempfile.gettempdir(), "wot1.json")
    wot1 = WebOfTrust(wot1_path)
    
    server = TCPServer(id1, 10001, None, wot1)
    await server.start()
    
    # Setup Node 2 (Client)
    id2_path = os.path.join(tempfile.gettempdir(), "n2.key")
    id2 = NodeIdentity(id2_path)
    id2.load_or_generate()
    
    wot2_path = os.path.join(tempfile.gettempdir(), "wot2.json")
    wot2 = WebOfTrust(wot2_path)
    
    # Client connects
    client_conn = ArchipelConnection(None, None, id2, wot2)
    print("Client: Connecting...")
    try:
        print("Client: Calling connect_and_do_client_handshake...")
        # Lancer le handshake (avec un timeout plus long pour voir où ça bloque)
        await asyncio.wait_for(client_conn.connect_and_do_client_handshake('127.0.0.1', 10001), timeout=5.0)
        print("Client: Handshake success!")
        
        # Test msg
        print("Client: Sending encrypted message...")
        await client_conn.send_encrypted_message(b"Hello Server")
        print("Client: Message sent!")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Client EXCEPTION: {e}")
    finally:
        server.stop()
        os.unlink(id1_path)
        os.unlink(id2_path)
        os.unlink(wot1_path)
        os.unlink(wot2_path)

if __name__ == "__main__":
    asyncio.run(main())    
