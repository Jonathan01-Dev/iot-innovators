"""Quick validation script for Archipel modules."""
import sys, os, tempfile, hashlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

print("=" * 50)
print("  ARCHIPEL — Validation rapide")
print("=" * 50)

# 1. Test PKI
from src.crypto.pki import NodeIdentity
kf = os.path.join(tempfile.gettempdir(), "test_arch.key")
id1 = NodeIdentity(kf)
id1.load_or_generate()
msg = b"Hello"
sig = id1.sign(msg)
assert NodeIdentity.verify(id1.public_key_bytes, msg, sig)
assert not NodeIdentity.verify(id1.public_key_bytes, b"Tampered", sig)
os.unlink(kf)
print("[OK] PKI: Ed25519 sign/verify")

# 2. Test Session
from src.crypto.session import SecureSession
s1 = SecureSession()
s2 = SecureSession()
s1.compute_shared_secret(s2.get_public_bytes())
s2.compute_shared_secret(s1.get_public_bytes())
assert s1.session_key == s2.session_key
assert len(s1.session_key) == 32
print("[OK] Session: X25519 + HKDF key exchange")

# 3. Test Encryption
from src.crypto.encryption import SecureChannel
ch1 = SecureChannel(s1.session_key)
ch2 = SecureChannel(s2.session_key)
nonce, ct = ch1.encrypt_message(b"Test E2E Archipel")
pt = ch2.decrypt_message(nonce, ct)
assert pt == b"Test E2E Archipel"
n1, _ = ch1.encrypt_message(b"A")
n2, _ = ch1.encrypt_message(b"A")
assert n1 != n2  # Unique nonces
print("[OK] Encryption: AES-256-GCM encrypt/decrypt, unique nonces")

# 4. Test Tamper detection
try:
    ch2.decrypt_message(nonce, bytes([b ^ 0xFF for b in ct]))
    assert False, "Should have raised"
except ValueError:
    pass
print("[OK] Encryption: tamper detection works")

# 5. Test Chunking
from src.core.chunking import FileManager, SharedFileIndex
idx = SharedFileIndex()
kf2 = os.path.join(tempfile.gettempdir(), "test_arch2.key")
id2 = NodeIdentity(kf2)
id2.load_or_generate()
fm = FileManager(id2, idx)

tf = os.path.join(tempfile.gettempdir(), "test_archipel_file.bin")
data = os.urandom(1024 * 1024)  # 1MB
with open(tf, "wb") as f:
    f.write(data)

manifest = fm.create_manifest(tf)
assert manifest["nb_chunks"] > 0
assert fm.verify_file(tf, manifest["file_id"])
assert not fm.verify_file(tf, "badhash")

chunk = fm.read_chunk(tf, 0)
assert fm.verify_chunk(chunk, manifest["chunks"][0]["hash"])
assert idx.get_filepath(manifest["file_id"]) is not None

os.unlink(tf)
os.unlink(kf2)
print("[OK] Chunking: manifest, verify_file, verify_chunk, index")

# 6. Test Packet
from src.network.packet import ArchipelPacket, PacketType
pkt = ArchipelPacket(PacketType.HELLO, id1.public_key_bytes, b"payload")
pkt.signature = b"\x00" * 64
serialized = pkt.serialize()
parsed = ArchipelPacket.parse(serialized)
assert parsed.pkt_type == PacketType.HELLO
assert parsed.payload == b"payload"
print("[OK] Packet: serialize/parse roundtrip")

# 7. Test WoT
from src.core.wot import WebOfTrust
wot_path = os.path.join(tempfile.gettempdir(), "test_wot.json")
wot = WebOfTrust(wot_path)
assert wot.verify_node("abc123")  # TOFU
assert wot.verify_node("abc123")  # Already known
wot.block_node("bad_node")
assert not wot.verify_node("bad_node")
os.unlink(wot_path)
print("[OK] Web of Trust: TOFU + block/revoke")

print()
print("=" * 50)
print("  TOUS LES TESTS PASSES !")
print("=" * 50)
