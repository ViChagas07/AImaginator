"""Porta de fetch de imagem por URL (edicao) — implementacao anti-SSRF."""

from __future__ import annotations

from typing import Protocol


class ImageFetcherPort(Protocol):
    async def fetch(self, url: str) -> bytes:
        """Baixa bytes de imagem de URL externa validada (allowlist + DNS).

        Levanta SSRFBlockedError para URL fora da politica.
        """
        ...

    async def fetch_base64_data_url(self, url: str) -> str:
        """Devolve data URL base64 (uso pelo adapter de agentes)."""
        ...
