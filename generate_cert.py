from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
import cryptography.x509 as x509
import datetime
import os

def generate_1024_cert():
    print("Generating 1024-bit RSA private key...")
    # Generate 1024-bit RSA Key (Required by ICONE/HiSilicon firmware)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )

    print("Generating self-signed certificate...")
    # Generate Self-Signed Certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"ICONE-Python-Client"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Valid for 10 years
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).sign(private_key, hashes.SHA256())

    # Write Private Key
    with open("key1024.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Write Certificate
    with open("cert1024.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print("Success! Created 'key1024.pem' and 'cert1024.pem' in the current directory.")

if __name__ == "__main__":
    generate_1024_cert()
