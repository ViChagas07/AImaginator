"""Provedores de geracao de imagem (detalhe de infra do adapter de agentes).

- StubImageProvider: determinista, para dev/testes/CI (sem chave real).
- HttpImageProvider: provedor real via API externa, protegido por
  Circuit Breaker (falha rapida) e Bulkhead (pool isolado).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from typing import Any, Protocol

from modules.image_generation.application.ports.image_agent_port import ProgressCallback
from modules.image_generation.domain.entities import Generation
from shared_kernel.errors import DomainError


class ImageProvider(Protocol):
    async def generate(self, generation: Generation, on_progress: ProgressCallback) -> str:
        """Devolve a URL da imagem gerada."""
        ...


class StubImageProvider:
    """Simula uma geracao: progride e devolve URL deterministica de placeholder.

    A URL derivada do hash do prompt e estavel (mesma entrada -> mesma
    imagem), o que permite asserts em testes e evals sem custo de API.
    """

    def __init__(self, *, storage_base_url: str = "https://picsum.photos") -> None:
        self._storage_base = storage_base_url.rstrip("/")

    async def generate(self, generation: Generation, on_progress: ProgressCallback) -> str:
        for percent in (15, 35, 60, 85):
            await on_progress(percent)
            await asyncio.sleep(0)  # cede a event loop (sem latencia artificial)
        seed = hashlib.sha256(generation.prompt.encode()).hexdigest()[:16]
        size = {"1:1": (1024, 1024), "3:4": (768, 1024), "16:9": (1280, 720), "9:16": (720, 1280)}[
            generation.aspect_ratio.value
        ]
        return f"{self._storage_base}/seed/{seed}/{size[0]}/{size[1]}"


class HttpImageProvider:
    """Chamada real ao provedor externo com resiliencia composta."""

    def __init__(
        self,
        *,
        http_client: Any,
        circuit_breaker: Any,
        bulkhead: Any,
        api_base_url: str,
        api_key: str,
    ) -> None:
        self._http = http_client
        self._cb = circuit_breaker
        self._bulkhead = bulkhead
        self._base_url = api_base_url.rstrip("/")
        self._api_key = api_key

    async def generate(self, generation: Generation, on_progress: ProgressCallback) -> str:
        async def _call() -> dict[str, Any]:
            response = await self._http.post(
                f"{self._base_url}/v1/images/generations",
                json={
                    "prompt": generation.prompt,
                    "negative_prompt": generation.negative_prompt,
                    "style": generation.style_preset.value,
                    "aspect_ratio": generation.aspect_ratio.value,
                    "source_image_url": generation.source_image_url,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120,
            )
            if response.status_code != 200:
                msg = f"Provedor de imagem respondeu HTTP {response.status_code}"
                raise DomainError(msg)
            return response.json()

        await on_progress(30)
        payload = await self._cb.call(lambda: self._bulkhead.run(_call))
        await on_progress(90)

        image_b64 = payload.get("image_base64")
        if image_b64:
            # Em producao: persistir no storage proprio e devolver a URL do CDN.
            base64.b64decode(image_b64)  # valida integridade
            raise DomainError("Storage proprio nao configurado para upload do resultado.")
        url = payload.get("image_url")
        if not url:
            raise DomainError("Resposta do provedor sem imagem utilizavel.")
        return str(url)
