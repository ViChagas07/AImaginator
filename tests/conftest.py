"""Fixtures compartilhadas dos testes (fakeredis, settings, fakes de portas)."""

from __future__ import annotations

import os
from uuid import uuid4

import fakeredis.aioredis
import pytest

from modules.users.contracts import User

# Testes nunca devem disparar `alembic upgrade head` no boot da app
# (o lifespan da API roda as migrations quando auto_migrate=True).
os.environ.setdefault("AUTO_MIGRATE", "false")
# Isola a suite do .env do desenvolvedor: modelos reais nunca rodam em teste.
os.environ["IMAGE_ENGINE"] = "stub"
os.environ["FEATURE_IMAGE_GENERATION_ENABLED"] = "true"


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def fake_sd_cli(tmp_path):
    from tests.fakes import create_fake_sd_cli

    return create_fake_sd_cli(tmp_path / "bin with spaces")


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
        item = self._items.get(generation_id)
        if item is not None and item.deleted_at is not None:
            return None
        return item

    async def save(self, generation):
        self._items[generation.id] = generation
        return generation

    async def delete(self, generation):
        from datetime import UTC, datetime

        generation.deleted_at = datetime.now(UTC)
        self._items[generation.id] = generation

    async def list_by_user(self, user_id, *, cursor, limit):
        items = [
            g
            for g in self._items.values()
            if g.user_id == user_id and g.deleted_at is None
        ]
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

    async def list_by_anonymous_session(self, anonymous_session_id, *, limit):
        items = [
            g
            for g in self._items.values()
            if g.anonymous_session_id == anonymous_session_id and g.deleted_at is None
        ]
        items.sort(key=lambda g: g.created_at, reverse=True)
        return items[:limit]

    async def reassign_anonymous_to_user(self, anonymous_session_id, user_id):
        migrated = 0
        for g in self._items.values():
            if g.anonymous_session_id == anonymous_session_id and g.user_id is None:
                g.user_id = user_id
                g.anonymous_session_id = None
                migrated += 1
        return migrated

    async def list_public_showcase(self, *, limit):
        from modules.image_generation.domain.entities import GenerationStatus

        items = [
            g
            for g in self._items.values()
            if g.status == GenerationStatus.DONE
            and g.result_image_url
            and g.user_id is not None
            and g.deleted_at is None
        ]
        items.sort(key=lambda g: g.created_at, reverse=True)
        return items[:limit]


class InMemoryObjectStorage:
    """Fake de ObjectStoragePort para testes (sem MinIO)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.deleted: list[str] = []

    async def put_object(self, key, data, *, content_type="image/png"):
        self.objects[key] = data
        self.content_types[key] = content_type

    async def get_object(self, key):
        return self.objects[key]

    async def presigned_get_url(self, key, *, expires_seconds=None):
        return f"https://storage.test/{key}?signature=test"

    async def delete_object(self, key):
        self.objects.pop(key, None)
        self.deleted.append(key)

    async def ensure_bucket(self):
        return None

    async def delete_objects_older_than(self, prefix, *, hours):
        stale = [key for key in self.objects if key.startswith(prefix)]
        for key in stale:
            self.objects.pop(key, None)
        return len(stale)


class FakeImageFetcher:
    """Fake de ImageFetcherPort: devolve um PNG valido pequeno."""

    def __init__(self, data: bytes | None = None) -> None:
        from modules.image_generation.adapters.ai_agents.providers import make_png_bytes

        self.data = data if data is not None else make_png_bytes(64, 48)
        self.calls: list[str] = []

    async def fetch(self, url):
        self.calls.append(url)
        return self.data

    async def fetch_base64_data_url(self, url):
        import base64

        return f"data:image/png;base64,{base64.b64encode(await self.fetch(url)).decode()}"


class SpyTaskQueue:
    """Spy de TaskQueuePort: registra enfileiramentos e kinds."""

    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.kinds: list[str] = []

    def enqueue_generation(self, generation_id, *, kind: str = "generate") -> None:
        self.enqueued.append(str(generation_id))
        self.kinds.append(kind)


class SpyEventPublisher:
    def __init__(self) -> None:
        self.events: list = []

    async def publish_progress(self, event) -> None:
        self.events.append(event)


class SpyPromptQuota:
    """Spy de PromptQuotaConsumerPort: registra principals sem consumir Redis."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, principal_id: str):
        self.calls.append(principal_id)


class PassThroughTopicGuard:
    """Fake de IPromptTopicGuard: aceita qualquer prompt sem alterar."""

    async def validate(self, prompt: str) -> str:
        return prompt
