"""Casos de uso do modulo auth."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from modules.auth.application.jwt_service import JWTService
from modules.auth.application.oidc_service import GoogleOIDCService
from modules.auth.domain.entities import AuthenticatedUser, SessionTokens
from modules.users.contracts import User, UserRepositoryPort


class StartGoogleLogin:
    """Inicia o fluxo SSO: devolve a URL de autorizacao do Google."""

    def __init__(self, oidc: GoogleOIDCService) -> None:
        self._oidc = oidc

    async def execute(self) -> str:
        return await self._oidc.build_authorization_url()


class CompleteGoogleLogin:
    """Conclui o callback OIDC: provisiona o usuario e emite a sessao."""

    def __init__(
        self,
        *,
        oidc: GoogleOIDCService,
        jwt_service: JWTService,
        user_repository: UserRepositoryPort,
    ) -> None:
        self._oidc = oidc
        self._jwt = jwt_service
        self._users = user_repository

    async def execute(self, *, code: str, state: str) -> tuple[SessionTokens, User]:
        profile = await self._oidc.exchange_code(code=code, state=state)

        user = await self._users.get_by_google_sub(profile.sub)
        if user is None:
            user = User(
                email=profile.email,
                name=profile.name,
                google_sub=profile.sub,
                avatar_url=profile.picture,
            )
        else:
            user.name = profile.name
            user.avatar_url = profile.picture
        await self._users.save(user)

        access, access_exp = self._jwt.issue_access_token(user.id)
        refresh, refresh_exp = self._jwt.issue_refresh_token(user.id)
        tokens = SessionTokens(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=datetime.fromtimestamp(access_exp, UTC),
            refresh_expires_at=datetime.fromtimestamp(refresh_exp, UTC),
        )
        return tokens, user


class GetAuthenticatedUser:
    """Resolve o usuario autenticado a partir do access token da sessao."""

    def __init__(self, *, jwt_service: JWTService, user_repository: UserRepositoryPort) -> None:
        self._jwt = jwt_service
        self._users = user_repository

    async def execute(self, access_token: str) -> AuthenticatedUser:
        user_id = self._jwt.verify_access_token(access_token)
        return AuthenticatedUser(user_id=user_id)


class RefreshSession:
    """Emite novo access token a partir de um refresh token valido."""

    def __init__(self, jwt_service: JWTService) -> None:
        self._jwt = jwt_service

    async def execute(self, refresh_token: str) -> tuple[str, int]:
        user_id = self._jwt.verify_refresh_token(refresh_token)
        return self._jwt.issue_access_token(user_id)
