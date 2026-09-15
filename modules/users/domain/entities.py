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
    google_sub: str  # subject OIDC — identidade estavel no provedor
    avatar_url: str | None = None
    id: UUID = field(default_factory=uuid4)
    generation_credits: int = DEFAULT_MONTHLY_CREDITS
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def has_quota(self) -> bool:
        return self.generation_credits > 0

    def consume_credit(self) -> None:
        """Debita 1 credito de geracao. Regra de negocio na entidade."""
        if not self.has_quota():
            from shared_kernel.errors import QuotaExceededError

            raise QuotaExceededError("Cota de geracoes esgotada.")
        self.generation_credits -= 1
        self.updated_at = datetime.now(UTC)
