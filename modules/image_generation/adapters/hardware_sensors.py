"""Sensores de hardware: LibreHardwareMonitor HTTP e fallback 'none'."""

from __future__ import annotations

import httpx
import psutil

from modules.image_generation.application.ports.hardware_sensor import (
    HardwareReading,
    HardwareSensorPort,
)


def _free_ram_mb() -> int:
    return int(psutil.virtual_memory().available // (1024 * 1024))


class NoneSensor(HardwareSensorPort):
    async def read(self) -> HardwareReading:
        return HardwareReading(
            max_temp_c=None,
            free_ram_mb=_free_ram_mb(),
            source="none",
            available=False,
        )


class LibreHardwareMonitorSensor(HardwareSensorPort):
    """Le o JSON do LibreHardwareMonitor (servidor web local)."""

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 2.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._http = http_client

    @staticmethod
    def _extract_temperatures(payload) -> list[float]:
        values: list[float] = []

        def walk(node) -> None:
            if isinstance(node, dict):
                text = str(node.get("Text") or node.get("text") or "").lower()
                value = node.get("Value", node.get("value"))
                if "temp" in text and isinstance(value, int | float):
                    values.append(float(value))
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(payload)
        return values

    async def read(self) -> HardwareReading:
        client = self._http or httpx.AsyncClient()
        owns = self._http is None
        try:
            response = await client.get(self._url, timeout=httpx.Timeout(self._timeout))
            response.raise_for_status()
            temps = self._extract_temperatures(response.json())
            return HardwareReading(
                max_temp_c=max(temps) if temps else None,
                free_ram_mb=_free_ram_mb(),
                source="librehardwaremonitor",
                available=bool(temps),
            )
        except Exception:
            return HardwareReading(
                max_temp_c=None,
                free_ram_mb=_free_ram_mb(),
                source="librehardwaremonitor",
                available=False,
            )
        finally:
            if owns:
                await client.aclose()
