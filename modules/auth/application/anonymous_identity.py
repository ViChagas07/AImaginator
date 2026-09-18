"""Identidade anonima de sessao — token assinado (anti-tamper).

Usuarios nao logados ganham um identificador anonimo estavel, assinado
com a SECRET_KEY via itsdangerous (TimestampSigner). O cliente nao
consegue forjar um identificador valido: qualquer tentativa de alterar
o token invalida a assinatura. Vincula cota (Bloco 1) e artes temporarias
(Bloco 3) a mesma sessao anonima.
"""

from __future__ import annotations

import secrets

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

_SALT = "aimaginator-anon"


def generate_anonymous_id() -> str:
    """Identificador opaco de alta entropia para uma sessao anonima."""
    return secrets.token_urlsafe(24)


def sign_anonymous_id(anonymous_id: str, *, secret_key: str) -> str:
    """Assina o identificador anonimo (o timestamp vira o TTL de validade)."""
    signer = TimestampSigner(secret_key, salt=_SALT)
    return signer.sign(anonymous_id.encode("ascii")).decode("ascii")


def unsign_anonymous_id(token: str, *, secret_key: str, max_age: int) -> str | None:
    """Valida assinatura/validade. Devolve o id ou None se invalido/expirado."""
    try:
        signer = TimestampSigner(secret_key, salt=_SALT)
        return signer.unsign(token, max_age=max_age).decode("ascii")
    except (BadSignature, SignatureExpired):
        return None
