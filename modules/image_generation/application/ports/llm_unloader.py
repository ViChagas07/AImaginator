"""Porta para descarregar o modelo do LM Studio antes do motor de imagem."""

from __future__ import annotations

from typing import Protocol


class LlmUnloaderPort(Protocol):
    async def unload_all(self) -> bool:
        """Tenta descarregar todos os modelos. Nunca levanta excecao."""
        ...
