"""PKCE (RFC 7636) + state anti-CSRF para o fluxo Authorization Code."""

from __future__ import annotations

import base64
import hashlib
import secrets


def generate_state() -> str:
    """Token opaco anti-CSRF vinculado ao inicio do fluxo de login."""
    return secrets.token_urlsafe(32)


def generate_code_verifier() -> str:
    """Verifier de alta entropia (43-128 chars, RFC 7636 secao 4.1)."""
    return secrets.token_urlsafe(64)[:128]


def code_challenge_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
