"""Testes do JWTService (emissao/verificacao/expiracao/tipo)."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from modules.auth.application.jwt_service import JWTService
from shared_kernel.errors import UnauthorizedError


def _service(access_ttl: int = 900, refresh_ttl: int = 3600) -> JWTService:
    return JWTService(
        secret_key="x" * 64,
        algorithm="HS256",
        access_ttl=access_ttl,
        refresh_ttl=refresh_ttl,
    )


@pytest.mark.unit
def test_roundtrip_access_token() -> None:
    jwt = _service()
    user_id = uuid4()
    token, exp = jwt.issue_access_token(user_id)
    assert exp > time.time()
    assert jwt.verify_access_token(token) == user_id


@pytest.mark.unit
def test_refresh_nao_vale_como_access() -> None:
    jwt = _service()
    refresh, _ = jwt.issue_refresh_token(uuid4())
    with pytest.raises(UnauthorizedError):
        jwt.verify_access_token(refresh)


@pytest.mark.unit
def test_token_adulterado_rejeitado() -> None:
    jwt = _service()
    token, _ = jwt.issue_access_token(uuid4())
    adulterado = token[:-3] + "abc"
    with pytest.raises(UnauthorizedError):
        jwt.verify_access_token(adulterado)


@pytest.mark.unit
def test_token_expirado_rejeitado() -> None:
    jwt = _service(access_ttl=-1)  # ja nasce expirado
    token, _ = jwt.issue_access_token(uuid4())
    with pytest.raises(UnauthorizedError):
        jwt.verify_access_token(token)


@pytest.mark.unit
def test_chave_errada_rejeitada() -> None:
    token, _ = _service().issue_access_token(uuid4())
    outro = JWTService(secret_key="y" * 64, algorithm="HS256", access_ttl=900, refresh_ttl=3600)
    with pytest.raises(UnauthorizedError):
        outro.verify_access_token(token)
