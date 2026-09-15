"""Vitrine publica de geracoes (galeria da landing/SEO) com cache SWR.

Leitura custosa (curadoria das melhores geracoes) cacheada com
Stale-While-Revalidate: nunca derruba o banco em pico de trafego
(anti cache stampede, spec secao 10).
"""

from __future__ import annotations

from modules.image_generation.adapters.cache.swr import SWRCache
from modules.image_generation.application.ports import GenerationRepositoryPort
from modules.image_generation.application.schemas import GenerationOutput
from modules.image_generation.application.use_cases.read_generations import _to_output

_SHOWCASE_KEY = "showcase:latest"
_SHOWCASE_SIZE = 24


class ListPublicShowcase:
    def __init__(self, *, generations: GenerationRepositoryPort, cache: SWRCache) -> None:
        self._generations = generations
        self._cache = cache

    async def execute(self) -> list[GenerationOutput]:
        async def load() -> list[dict]:
            items = await self._generations.list_public_showcase(limit=_SHOWCASE_SIZE)
            return [_to_output(g).model_dump(mode="json") for g in items]

        raw_items = await self._cache.get_or_load(
            _SHOWCASE_KEY, load, fresh_ttl_seconds=60, stale_ttl_seconds=600
        )
        return [GenerationOutput(**item) for item in raw_items]
