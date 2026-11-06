"""Politica de timeout do SSE derivada dos timeouts de geracao/edicao."""

from __future__ import annotations

from typing import Protocol

STREAM_MARGIN_SECONDS = 60
ASSISTANT_STREAM_MARGIN_SECONDS = 30


class StreamTimeoutSettings(Protocol):
    generation_timeout_seconds: int
    edit_timeout_seconds: int
    llm_timeout_seconds: float


def stream_timeout_seconds(settings: StreamTimeoutSettings) -> int:
    """Maior job (LLM + motor) + margem para receber o evento final."""
    import math

    llm_timeout = float(getattr(settings, "llm_timeout_seconds", 0) or 0)
    assistant_margin = math.ceil(llm_timeout)
    if assistant_margin > 0:
        assistant_margin += ASSISTANT_STREAM_MARGIN_SECONDS
    upscale_timeout = int(getattr(settings, "upscale_timeout_seconds", 0) or 0)
    return (
        max(
            settings.generation_timeout_seconds,
            settings.edit_timeout_seconds,
            upscale_timeout,
        )
        + assistant_margin
        + STREAM_MARGIN_SECONDS
    )
