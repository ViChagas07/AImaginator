"""Guarda termica e de RAM antes/durante jobs de imagem."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports.hardware_sensor import (
    HardwareReading,
    HardwareSensorPort,
)
from modules.observability.logging_config import get_logger
from modules.observability.metrics import (
    HARDWARE_ABORTS_TOTAL,
    HARDWARE_FREE_RAM_BYTES,
    HARDWARE_SENSOR_MISSING_TOTAL,
    HARDWARE_TEMPERATURE_C,
)
from shared_kernel.security_errors import (
    HardwareBusyError,
    ResourceAbortError,
    ThermalAbortError,
)

logger = get_logger(__name__)


class ThermalGuard:
    def __init__(
        self,
        *,
        settings,
        sensor: HardwareSensorPort,
        cooling_callback: Callable[[int, str], None] | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._sensor = sensor
        self._cooling_callback = cooling_callback
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep or asyncio.sleep

    def _record(self, reading: HardwareReading) -> None:
        HARDWARE_FREE_RAM_BYTES.set(reading.free_ram_mb * 1024 * 1024)
        if reading.max_temp_c is not None:
            HARDWARE_TEMPERATURE_C.set(reading.max_temp_c)
        if not reading.available:
            HARDWARE_SENSOR_MISSING_TOTAL.inc()

    async def before_job(self, *, locale: str = "pt-BR") -> None:
        if not self._settings.thermal_guard_enabled:
            return
        deadline = self._clock().timestamp() + self._settings.cooldown_after_abort_seconds
        while True:
            reading = await self._sensor.read()
            self._record(reading)
            if not reading.available or reading.max_temp_c is None:
                logger.warning(
                    "hardware_sensor_unavailable",
                    source=reading.source,
                )
                return
            if reading.max_temp_c <= self._settings.start_temp_max_c:
                return
            logger.warning(
                "hardware_too_hot_waiting",
                temperature_c=reading.max_temp_c,
                limit_c=self._settings.start_temp_max_c,
            )
            if self._clock().timestamp() >= deadline:
                raise HardwareBusyError(message_for("hardware_busy", locale))
            await self._sleep(self._settings.hw_sensor_interval_seconds)

    async def check_running(self, *, locale: str = "pt-BR") -> None:
        if not self._settings.thermal_guard_enabled:
            return
        reading = await self._sensor.read()
        self._record(reading)
        if not reading.available or reading.max_temp_c is None:
            if reading.free_ram_mb < self._settings.min_free_ram_abort_mb:
                self._abort("resource", "resource_abort", locale)
            return
        if reading.max_temp_c >= self._settings.abort_temp_c:
            self._abort("thermal", "thermal_abort", locale)
        if reading.free_ram_mb < self._settings.min_free_ram_abort_mb:
            self._abort("resource", "resource_abort", locale)

    def _abort(self, reason: str, code: str, locale: str) -> None:
        HARDWARE_ABORTS_TOTAL.labels(reason=reason).inc()
        if self._cooling_callback is not None:
            try:
                self._cooling_callback(self._settings.cooldown_after_abort_seconds, code)
            except Exception:
                logger.warning("hardware_cooling_callback_failed", exc_info=True)
        logger.error(
            "hardware_abort",
            reason=reason,
            code=code,
        )
        if reason == "thermal":
            raise ThermalAbortError(message_for(code, locale))
        raise ResourceAbortError(message_for(code, locale))
