"""Gera certificado C2PA APENAS PARA DESENVOLVIMENTO (autoassinado).

NAO use em producao: producao exige certificado de uma CA confiavel.
Uso:
    poetry run python tools/gen_dev_c2pa_cert.py --out-dir tools/c2pa-dev
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tools/c2pa-dev")
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "AImaginator DEV ONLY")]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_path = out / "dev-key.pem"
    cert_path = out / "dev-cert.pem"
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print("DEV ONLY: certificado autoassinado gerado.")
    print(f"cert={cert_path} key={key_path}")
    print("Nunca use este certificado em producao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
