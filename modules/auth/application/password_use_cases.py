"""Casos de uso de autenticacao por email/senha (cadastro + login)."""

from __future__ import annotations

from datetime import UTC, datetime

from modules.auth.application.jwt_service import JWTService
from modules.auth.application.password_hasher import hash_password, verify_password
from modules.auth.domain.entities import SessionTokens
from modules.users.contracts import User, UserRepositoryPort
from shared_kernel.errors import ConflictError, UnauthorizedError


def _issue_session(jwt_service: JWTService, user: User) -> SessionTokens:
    access, access_exp = jwt_service.issue_access_token(user.id)
    refresh, refresh_exp = jwt_service.issue_refresh_token(user.id)
    return SessionTokens(
        access_token=access,
        refresh_token=refresh,
        access_expires_at=datetime.fromtimestamp(access_exp, UTC),
        refresh_expires_at=datetime.fromtimestamp(refresh_exp, UTC),
    )


class SignUpWithEmail:
    """Cadastro de conta com email/senha (email e a identidade de login)."""

    def __init__(
        self, *, user_repository: UserRepositoryPort, jwt_service: JWTService
    ) -> None:
        self._users = user_repository
        self._jwt = jwt_service

    async def execute(self, *, name: str, email: str, password: str) -> tuple[SessionTokens, User]:
        normalized = email.strip().lower()
        existing = await self._users.get_by_email(normalized)
        if existing is not None:
            raise ConflictError("Ja existe uma conta com este e-mail.")

        user = User(email=normalized, name=name.strip(), password_hash=hash_password(password))
        await self._users.save(user)
        return _issue_session(self._jwt, user), user


class LoginWithEmail:
    """Login com email/senha (erro generico anti-enumeracao de contas)."""

    def __init__(
        self, *, user_repository: UserRepositoryPort, jwt_service: JWTService
    ) -> None:
        self._users = user_repository
        self._jwt = jwt_service

    async def execute(self, *, email: str, password: str) -> tuple[SessionTokens, User]:
        user = await self._users.get_by_email(email.strip().lower())
        if user is None or not user.password_hash:
            raise UnauthorizedError("Credenciais invalidas.")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Credenciais invalidas.")
        return _issue_session(self._jwt, user), user
