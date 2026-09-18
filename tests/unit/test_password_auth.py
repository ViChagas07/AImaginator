"""Testes da autenticacao por email/senha (hash + casos de uso)."""

from __future__ import annotations

import pytest

from modules.auth.application.jwt_service import JWTService
from modules.auth.application.password_hasher import hash_password, verify_password
from modules.auth.application.password_use_cases import LoginWithEmail, SignUpWithEmail
from shared_kernel.errors import ConflictError, UnauthorizedError
from tests.conftest import InMemoryUserRepository


def _jwt() -> JWTService:
    return JWTService(
        secret_key="x" * 32, algorithm="HS256", access_ttl=900, refresh_ttl=2592000
    )


@pytest.mark.unit
class TestPasswordHasher:
    def test_hash_e_verify_ok(self) -> None:
        hashed = hash_password("senha-segura-123")
        assert hashed != "senha-segura-123"
        assert verify_password("senha-segura-123", hashed)

    def test_senha_errada_falha(self) -> None:
        hashed = hash_password("correta")
        assert not verify_password("errada", hashed)

    def test_salt_unico_gera_hashes_diferentes(self) -> None:
        assert hash_password("mesma-senha") != hash_password("mesma-senha")


@pytest.mark.unit
class TestEmailPasswordUseCases:
    async def test_signup_emite_sessao_e_salva_hash(self) -> None:
        users = InMemoryUserRepository()
        tokens, user = await SignUpWithEmail(
            user_repository=users, jwt_service=_jwt()
        ).execute(name="Ada Lovelace", email="ADA@Example.com", password="segredo123")
        assert tokens.access_token
        assert user.email == "ada@example.com"  # normalizado
        assert user.password_hash is not None
        assert verify_password("segredo123", user.password_hash)

    async def test_signup_email_duplicado_409(self) -> None:
        users = InMemoryUserRepository()
        use_case = SignUpWithEmail(user_repository=users, jwt_service=_jwt())
        await use_case.execute(name="A", email="a@x.com", password="segredo123")
        with pytest.raises(ConflictError):
            await use_case.execute(name="B", email="a@x.com", password="outra-senha")

    async def test_login_ok(self) -> None:
        users = InMemoryUserRepository()
        await SignUpWithEmail(user_repository=users, jwt_service=_jwt()).execute(
            name="A", email="a@x.com", password="segredo123"
        )
        tokens, user = await LoginWithEmail(
            user_repository=users, jwt_service=_jwt()
        ).execute(email="A@X.com", password="segredo123")
        assert tokens.access_token
        assert user.email == "a@x.com"

    async def test_login_senha_invalida_401(self) -> None:
        users = InMemoryUserRepository()
        await SignUpWithEmail(user_repository=users, jwt_service=_jwt()).execute(
            name="A", email="a@x.com", password="segredo123"
        )
        with pytest.raises(UnauthorizedError):
            await LoginWithEmail(user_repository=users, jwt_service=_jwt()).execute(
                email="a@x.com", password="senha-errada"
            )

    async def test_login_email_inexistente_401(self) -> None:
        use_case = LoginWithEmail(
            user_repository=InMemoryUserRepository(), jwt_service=_jwt()
        )
        with pytest.raises(UnauthorizedError):
            await use_case.execute(email="ninguem@x.com", password="qualquer")
