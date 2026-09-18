"""Entidade de dominio do modulo prompt_quota — pura, sem framework."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PromptQuota:
    """Estado da cota de prompts de um principal (usuario ou anonimo)."""

    chances_remaining: int
    chances_total: int
    next_available_at: datetime | None

    @property
    def exhausted(self) -> bool:
        return self.chances_remaining <= 0
