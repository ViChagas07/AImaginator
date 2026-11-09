"""Helpers da biblioteca: tags, tokens e retentativa."""

from __future__ import annotations

import secrets
from uuid import uuid4

import pytest

from modules.image_generation.adapters.repositories.library_repository import (
    normalize_tag,
    token_hash,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from shared_kernel.errors import DomainError


@pytest.mark.unit
def test_normaliza_tag_e_rejeita_invalidas() -> None:
    assert normalize_tag("  Paisagem   Noite ") == "paisagem noite"
    with pytest.raises(DomainError):
        normalize_tag("")
    with pytest.raises(DomainError):
        normalize_tag("x" * 33)
    with pytest.raises(DomainError):
        normalize_tag("tag<script>")


@pytest.mark.unit
def test_token_hash_e_estavel_e_token_tem_entropia() -> None:
    raw = secrets.token_urlsafe(32)
    assert len(raw) >= 40
    assert token_hash(raw) == token_hash(raw)
    assert token_hash(raw) != token_hash(secrets.token_urlsafe(32))
    assert len(token_hash(raw)) == 64


@pytest.mark.unit
def test_retry_apenas_para_falhas_de_sistema() -> None:
    generation = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="x")
    generation.transition_to(GenerationStatus.PROCESSING)
    generation.transition_to(GenerationStatus.FAILED, error="x", error_code="engine_timeout")
    assert generation.can_retry() is True

    blocked = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="x")
    blocked.transition_to(GenerationStatus.PROCESSING)
    blocked.transition_to(GenerationStatus.FAILED, error="x", error_code="content_blocked_nsfw")
    assert blocked.can_retry() is False
