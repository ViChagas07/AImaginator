"""Testes do servico de moderacao e penalidades (3 niveis + janela)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import REGISTRY

from modules.image_generation.application.services.moderation import ModerationService
from modules.image_generation.domain.moderation import (
    ModerationCategory,
    ModerationLayer,
)
from tests.conftest import InMemoryUserRepository


class FakeModerationRepository:
    def __init__(self) -> None:
        self.events = []

    async def add(self, event):
        self.events.append(event)

    async def count_since(
        self, *, since, user_id=None, anonymous_session_id=None, ip_hash=None
    ) -> int:
        total = 0
        for event in self.events:
            if event.created_at is None or event.created_at < since:
                continue
            if user_id is not None and event.user_id == user_id:
                total += 1
            elif user_id is None and (
                (anonymous_session_id and event.anonymous_session_id == anonymous_session_id)
                or (ip_hash and event.ip_hash == ip_hash)
            ):
                total += 1
        return total


class FakePenaltyStore:
    def __init__(self) -> None:
        self.blocks: dict[str, datetime] = {}

    async def get_block_until(self, *, keys):
        values = [self.blocks[k] for k in keys if k in self.blocks]
        return max(values) if values else None

    async def set_block(self, *, keys, until):
        for key in keys:
            self.blocks[key] = until


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _service(user_repo, *, store_prompt_text=False, clock=None, repo=None, penalty=None):
    return ModerationService(
        events=repo or FakeModerationRepository(),
        users=user_repo,
        penalty_store=penalty or FakePenaltyStore(),
        warn_at=3,
        block_at=5,
        review_at=10,
        block_minutes=60,
        review_block_hours=24,
        window_hours=24,
        store_prompt_text=store_prompt_text,
        clock=clock or Clock(),
    )


async def _record(service, user, *, category=ModerationCategory.NSFW, text="prompt proibido"):
    return await service.record_moderation(
        category=category,
        layer=ModerationLayer.LLM,
        confidence=0.9,
        locale="en",
        prompt_text=text,
        user=user,
        anonymous_session_id=None,
        ip_hash="ip-hash",
    )


@pytest.mark.unit
async def test_niveis_de_penalidade(sample_user) -> None:
    users = InMemoryUserRepository(sample_user)
    clock = Clock()
    service = _service(users, clock=clock)
    outcomes = [await _record(service, sample_user) for _ in range(10)]

    assert outcomes[1].level == 0
    assert outcomes[2].level == 1
    assert outcomes[2].warning_level == 1
    assert outcomes[2].warning_message
    assert (REGISTRY.get_sample_value(
        "aimaginator_penalties_total", {"level": "1"}
    ) or 0) >= 1
    assert outcomes[4].level == 2
    assert outcomes[4].blocked_until == clock.now + timedelta(minutes=60)
    assert outcomes[9].level == 3
    assert outcomes[9].blocked_until == clock.now + timedelta(hours=24)
    assert sample_user.moderation_flag is True


@pytest.mark.unit
async def test_prompt_nao_e_armazenado_por_padrao(sample_user) -> None:
    repo = FakeModerationRepository()
    service = _service(InMemoryUserRepository(sample_user), repo=repo)
    await _record(service, sample_user, text="segredo do usuario")

    event = repo.events[0]
    assert event.prompt_text is None
    assert event.prompt_hash == hashlib.sha256(b"segredo do usuario").hexdigest()
    assert event.prompt_length == len("segredo do usuario")


@pytest.mark.unit
async def test_prompt_e_truncado_quando_flag_ativa(sample_user) -> None:
    repo = FakeModerationRepository()
    service = _service(
        InMemoryUserRepository(sample_user), repo=repo, store_prompt_text=True
    )
    await _record(service, sample_user, text="x" * 500)
    assert len(repo.events[0].prompt_text) == 200


@pytest.mark.unit
async def test_anonimo_usa_bloqueio_por_sessao_e_ip(sample_user) -> None:
    clock = Clock()
    penalty = FakePenaltyStore()
    service = _service(
        InMemoryUserRepository(sample_user), clock=clock, penalty=penalty
    )
    for _ in range(5):
        await service.record_moderation(
            category=ModerationCategory.HATE,
            layer=ModerationLayer.LLM,
            confidence=0.9,
            locale="en",
            prompt_text="odio",
            user=None,
            anonymous_session_id="anon-1",
            ip_hash="ip-1",
        )
    assert penalty.blocks["anon:anon-1"] == clock.now + timedelta(minutes=60)
    assert penalty.blocks["ip:ip-1"] == clock.now + timedelta(minutes=60)

    blocked = await service.current_block(
        user=None, anonymous_session_id="anon-1", ip_hash="ip-1"
    )
    assert blocked == clock.now + timedelta(minutes=60)


@pytest.mark.unit
async def test_janela_de_24h_ignora_eventos_antigos(sample_user) -> None:
    clock = Clock()
    repo = FakeModerationRepository()
    service = _service(InMemoryUserRepository(sample_user), clock=clock, repo=repo)
    old = clock.now - timedelta(hours=25)
    for _ in range(5):
        await _record(service, sample_user)
    from dataclasses import replace

    repo.events = [replace(event, created_at=old) for event in repo.events]

    outcome = await _record(service, sample_user)
    assert outcome.level == 0


@pytest.mark.unit
async def test_current_block_le_db_do_usuario(sample_user) -> None:
    clock = Clock()
    service = _service(InMemoryUserRepository(sample_user), clock=clock)
    sample_user.moderation_blocked_until = clock.now + timedelta(minutes=30)
    blocked = await service.current_block(
        user=sample_user, anonymous_session_id=None, ip_hash=None
    )
    assert blocked == sample_user.moderation_blocked_until


@pytest.mark.unit
async def test_categoria_e_layer_sao_gravados(sample_user) -> None:
    repo = FakeModerationRepository()
    service = _service(InMemoryUserRepository(sample_user), repo=repo)
    await _record(service, sample_user, category=ModerationCategory.GORE)
    assert repo.events[0].category is ModerationCategory.GORE
    assert repo.events[0].layer is ModerationLayer.LLM
