"""Fixtures compartilhadas dos testes (fakeredis, settings, fakes de portas)."""

from __future__ import annotations

from uuid import uuid4

import fakeredis.aioredis
import pytest

from modules.users.contracts import User


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def sample_user() -> User:
    return User(
        id=uuid4(),
        email="ada@example.com",
        name="Ada Lovelace",
        google_sub="google-sub-123",
        generation_credits=5,
    )


class InMemoryUserRepository:
    """Fake de UserRepositoryPort para testes de casos de uso."""

    def __init__(self, user: User | None = None) -> None:
        self._users: dict = {}
        if user is not None:
            self._users[user.id] = user

    async def get_by_id(self, user_id):
        return self._users.get(user_id)

    async def get_by_google_sub(self, google_sub: str):
        return next((u for u in self._users.values() if u.google_sub == google_sub), None)

    async def get_by_email(self, email: str):
        return next((u for u in self._users.values() if u.email == email.lower()), None)

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user


class InMemoryGenerationRepository:
    """Fake de GenerationRepositoryPort."""

    def __init__(self) -> None:
        self._items: dict = {}

    async def get_by_id(self, generation_id):
        return self._items.get(generation_id)

    async def save(self, generation):
        self._items[generation.id] = generation
        return generation

    async def list_by_user(self, user_id, *, cursor, limit):
        items = [g for g in self._items.values() if g.user_id == user_id]
        items.sort(key=lambda g: (g.created_at, g.id), reverse=True)
        if cursor is not None:
            cursor_item = self._items.get(cursor)
            if cursor_item is not None:
                items = [
                    g
                    for g in items
                    if (g.created_at, g.id) < (cursor_item.created_at, cursor_item.id)
                ]
        return items[:limit]

    async def list_public_showcase(self, *, limit):
        from modules.image_generation.domain.entities import GenerationStatus

        items = [
            g
            for g in self._items.values()
            if g.status == GenerationStatus.DONE and g.result_image_url
        ]
        items.sort(key=lambda g: g.created_at, reverse=True)
        return items[:limit]


class SpyTaskQueue:
    """Spy de TaskQueuePort: registra enfileiramentos."""

    def __init__(self) -> None:
        self.enqueued: list[str] = []

    def enqueue_generation(self, generation_id, *, priority: bool = False) -> None:
        self.enqueued.append(str(generation_id))


class SpyEventPublisher:
    def __init__(self) -> None:
        self.events: list = []

    async def publish_progress(self, event) -> None:
        self.events.append(event)
