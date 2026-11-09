"""Guarda termica com sensor falso (sem hardware real)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from modules.image_generation.application.ports.hardware_sensor import HardwareReading
from modules.image_generation.application.services.thermal_guard import ThermalGuard
from shared_kernel.security_errors import (
    HardwareBusyError,
    ResourceAbortError,
    ThermalAbortError,
)


class _Sensor:
    def __init__(self, readings) -> None:
        self.readings = list(readings)

    async def read(self) -> HardwareReading:
        return self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]


def _settings(**overrides):
    values = {
        "thermal_guard_enabled": True,
        "start_temp_max_c": 80.0,
        "abort_temp_c": 92.0,
        "cooldown_after_abort_seconds": 10,
        "min_free_ram_abort_mb": 512,
        "hw_sensor_interval_seconds": 1.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _guard(sensor, settings=None, cooling=None):
    now = datetime(2026, 1, 1, tzinfo=UTC)

    async def sleep(_seconds):
        nonlocal now
        now += timedelta(seconds=1)

    return ThermalGuard(
        settings=settings or _settings(),
        sensor=sensor,
        cooling_callback=cooling,
        clock=lambda: now,
        sleep=sleep,
    )


@pytest.mark.unit
async def test_espera_resfriar_antes_do_job() -> None:
    sensor = _Sensor(
        [
            HardwareReading(85, 4096, "fake"),
            HardwareReading(75, 4096, "fake"),
        ]
    )
    await _guard(sensor).before_job(locale="en")


@pytest.mark.unit
async def test_persistindo_quente_falha_hardware_busy() -> None:
    sensor = _Sensor([HardwareReading(90, 4096, "fake")])
    with pytest.raises(HardwareBusyError):
        await _guard(sensor).before_job(locale="en")


@pytest.mark.unit
async def test_aborto_termico_no_meio_e_cooling() -> None:
    calls: list[tuple[int, str]] = []
    guard = _guard(
        _Sensor([HardwareReading(95, 4096, "fake")]),
        cooling=lambda seconds, reason: calls.append((seconds, reason)),
    )
    with pytest.raises(ThermalAbortError):
        await guard.check_running(locale="en")
    assert calls == [(10, "thermal_abort")]


@pytest.mark.unit
async def test_aborto_por_ram_baixa() -> None:
    guard = _guard(_Sensor([HardwareReading(None, 100, "none", available=False)]))
    with pytest.raises(ResourceAbortError):
        await guard.check_running(locale="en")


@pytest.mark.unit
async def test_sensor_ausente_nao_bloqueia_inicio() -> None:
    guard = _guard(_Sensor([HardwareReading(None, 4096, "none", available=False)]))
    await guard.before_job(locale="en")
    await guard.check_running(locale="en")


@pytest.mark.unit
async def test_guarda_desligada_e_noop() -> None:
    guard = _guard(
        _Sensor([HardwareReading(99, 10, "fake")]),
        settings=_settings(thermal_guard_enabled=False),
    )
    await guard.before_job(locale="en")
    await guard.check_running(locale="en")
