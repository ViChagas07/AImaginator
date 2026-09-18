"""Hash de senhas com PBKDF2-HMAC-SHA256 (stdlib, sem dependencia nova).

Formato de armazenamento: `pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>`.
Verificacao em tempo constante (hmac.compare_digest) contra timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Gera hash salgado de uma senha em texto plano."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    """Compara a senha com o hash armazenado (tempo constante)."""
    try:
        algorithm, iterations_raw, salt, expected = encoded.split("$")
        iterations = int(iterations_raw)
    except (ValueError, AttributeError):
        return False
    if algorithm != _ALGORITHM:
        return False
    computed = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()
    return hmac.compare_digest(computed, expected)
