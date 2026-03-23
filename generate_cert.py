# === Jarvis 4.0 — Self-Signed SSL Certificate Generator ===
# Run ONCE: python generate_cert.py
# Then restart Jarvis — mic will work in ALL browsers on your network

import os
import datetime
import ipaddress

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_DIR = os.path.join(BASE_DIR, "certs")
CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE  = os.path.join(CERT_DIR, "key.pem")

os.makedirs(CERT_DIR, exist_ok=True)

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("[ERROR] cryptography library not found.")
    print("        Run:  pip install cryptography")
    exit(1)

print("[Jarvis] Generating self-signed SSL certificate...")

# --- Private Key ---
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# --- Certificate ---
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME,          u"Jarvis"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,    u"Jarvis AI"),
])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))  # 10 years
    .add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u"localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            x509.IPAddress(ipaddress.IPv4Address("192.168.X.X")),   # Replace with your Jarvis server LAN IP
            # x509.IPAddress(ipaddress.IPv4Address("192.168.X.X")),  # Optional: add more LAN IPs
        ]),
        critical=False,
    )
    .sign(key, hashes.SHA256())
)

# --- Write files ---
with open(CERT_FILE, "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

with open(KEY_FILE, "wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()
    ))

print(f"[Jarvis] Certificate written to: {CERT_FILE}")
print(f"[Jarvis] Private key written to: {KEY_FILE}")
print()
print("=" * 55)
print("  Done. Now restart Jarvis with: python app.py")
print()
print("  Access Jarvis at: https://YOUR-LAN-IP:5000")
print()
print("  First visit on each device:")
print("  Samsung Internet → 'Details' → 'Visit anyway'")
print("  Chrome           → 'Advanced' → 'Proceed'")
print("  You only need to do this ONCE per device.")
print("=" * 55)
