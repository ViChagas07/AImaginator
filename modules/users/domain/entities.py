"""Entidade de dominio User — pura, zero dependencia de framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

DEFAULT_MONTHLY_CREDITS = 50


@dataclass(slots=True)
class User:
    """Usuario do AImaginator (provisionado via SSO Google/OIDC)."""

    email: str
    name: str
    google_sub: str | None = None  # subject OIDC — identidade estavel no provedor
    password_hash: str | None = None  # apenas para contas com email/senha
    avatar_url: str | None = None
    bio: str | None = None
    handle: str | None = None
    id: UUID = field(default_factory=uuid4)
    generation_credits: int = DEFAULT_MONTHLY_CREDITS
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def has_quota(self) -> bool:
        return self.generation_credits > 0

    def has_alternative_login(self) -> bool:
        """Indica se existe outro metodo de login alem do SSO Google.

        Um usuario so pode desconectar o Google (unico provedor OAuth)
        se tiver uma senha cadastrada como metodo alternativo.
        """
        return self.password_hash is not None

    def consume_credit(self) -> None:
        """Debita 1 credito de geracao. Regra de negocio na entidade."""
        if not self.has_quota():
            from shared_kernel.errors import QuotaExceededError

            raise QuotaExceededError("Cota de geracoes esgotada.")
        self.generation_credits -= 1
        self.updated_at = datetime.now(UTC)


@dataclass(slots=True)
class UserSettings:
    """Preferencias do usuario (persistidas em user_settings)."""

    user_id: UUID
    # Aparência
    theme: str = "system"  # dark | light | system
    bold_text: bool = False
    font_size: str = "medium"  # small | medium | large | xl
    element_spacing: str = "comfortable"  # compact | comfortable | spacious
    # Idioma e Região
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"
    # Acessibilidade
    high_contrast: bool = False
    screen_reader_optimized: bool = False
    keyboard_navigation: bool = False
    focus_indicator: bool = False
    dyslexia_font: bool = False
    reduced_motion: bool = False
    # Notificações
    email_notifications: bool = True
    push_notifications: bool = True
    desktop_notifications: bool = True
    sound_notifications: bool = True
    summary_frequency: str = "weekly"  # daily | weekly | never
    notification_email: str | None = None
    # Privacidade
    privacy_policy_version: str | None = None
    terms_version: str | None = None
    consented_at: datetime | None = None
    # Avançado
    developer_mode: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
