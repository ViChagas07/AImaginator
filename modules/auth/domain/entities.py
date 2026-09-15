"""Entidades de dominio do modulo auth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionTokens:
    """Par de tokens da sessao propria da aplicacao (nao confundir com
    tokens do Google — estes nunca saem do backend)."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    """Perfil minimo retornado pelo OIDC do Google."""

    sub: str
    email: str
    name: str
    picture: str | None


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Contexto de autenticacao resolvido a partir do JWT da sessao."""

    user_id: UUID
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
