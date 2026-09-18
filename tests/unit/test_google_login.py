"""Testes do caso de uso CompleteGoogleLogin (provisionamento via SSO Google).

Cobre: conta nova, conta de email/senha pre-existente (vinculo sem duplicar)
e conta Google ja existente (atualiza nome/avatar).
"""

from __future__ import annotations

import pytest

from modules.auth.application.jwt_service import JWTService
from modules.auth.application.use_cases import CompleteGoogleLogin
from modules.auth.domain.entities import GoogleProfile
from modules.users.contracts import User
from tests.conftest import InMemoryUserRepository


class _FakeOIDC:
    """Fake de GoogleOIDCService — devolve o perfil diretamente."""

    def __init__(self, profile: GoogleProfile) -> None:
        self._profile = profile

    async def exchange_code(self, *, code: str, state: str) -> GoogleProfile:
        return self._profile


def _jwt() -> JWTService:
    return JWTService(
        secret_key="x" * 32, algorithm="HS256", access_ttl=900, refresh_ttl=2592000
    )


_PROFILE = GoogleProfile(
    sub="google-sub-999",
    email="ada@example.com",
    name="Ada Lovelace",
    picture="https://img.example/ada.png",
)


@pytest.mark.unit
class TestCompleteGoogleLogin:
    async def test_conta_nova_e_provisionada(self) -> None:
        users = InMemoryUserRepository()
        tokens, user = await CompleteGoogleLogin(
            oidc=_FakeOIDC(_PROFILE),
            jwt_service=_jwt(),
            user_repository=users,
        ).execute(code="c", state="s")
        assert tokens.access_token
        assert user.email == "ada@example.com"
        assert user.google_sub == "google-sub-999"
        assert user.avatar_url == "https://img.example/ada.png"

    async def test_conta_email_existente_e_vinculada_sem_duplicar(self) -> None:
        existing = User(email="ada@example.com", name="Ada", password_hash="hash")
        users = InMemoryUserRepository(existing)
        _, user = await CompleteGoogleLogin(
            oidc=_FakeOIDC(_PROFILE),
            jwt_service=_jwt(),
            user_repository=users,
        ).execute(code="c", state="s")
        # Mesmo id (nao criou duplicada) e google_sub vinculado.
        assert user.id == existing.id
        assert user.google_sub == "google-sub-999"
        assert user.name == "Ada Lovelace"

    async def test_conta_google_existente_atualiza_nome_e_avatar(self) -> None:
        existing = User(
            email="ada@example.com",
            name="Nome Antigo",
            google_sub="google-sub-999",
            avatar_url=None,
        )
        users = InMemoryUserRepository(existing)
        _, user = await CompleteGoogleLogin(
            oidc=_FakeOIDC(_PROFILE),
            jwt_service=_jwt(),
            user_repository=users,
        ).execute(code="c", state="s")
        assert user.id == existing.id
        assert user.name == "Ada Lovelace"
        assert user.avatar_url == "https://img.example/ada.png"
