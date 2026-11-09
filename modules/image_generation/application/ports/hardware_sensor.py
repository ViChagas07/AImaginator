"""Porta de sensores de hardware (temperatura/RAM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HardwareReading:
    max_temp_c: float | None
    free_ram_mb: int
    source: str
    available: bool = True


class HardwareSensorPort(Protocol):
    async def read(self) -> HardwareReading: ...
