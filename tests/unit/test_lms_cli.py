"""Testes do descarregamento do LM Studio via lms CLI (fake executable)."""

from __future__ import annotations

import asyncio
import os

import pytest
from prometheus_client import REGISTRY

from modules.image_generation.adapters.lms_cli import LmsCliUnloader


class _Process:
    def __init__(self, *, returncode: int = 0, stderr: bytes = b"", hang: bool = False) -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.hang = hang
        self.killed = False

    async def communicate(self):
        if self.hang:
            await asyncio.sleep(10)
        return b"", self.stderr

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode


def _metric(outcome: str) -> float:
    return REGISTRY.get_sample_value("aimaginator_llm_unload_total", {"outcome": outcome}) or 0


@pytest.mark.unit
async def test_sucesso_executa_sem_shell() -> None:
    calls: list[tuple] = []

    async def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return _Process()

    before = _metric("success")
    unloader = LmsCliUnloader(cli_path="C:/LM Studio/lms.exe", process_factory=factory)
    assert await unloader.unload_all() is True

    args, kwargs = calls[0]
    assert args == ("C:/LM Studio/lms.exe", "unload", "--all")
    assert "shell" not in kwargs
    assert kwargs["stdout"] == asyncio.subprocess.DEVNULL
    assert _metric("success") == before + 1


@pytest.mark.unit
async def test_cli_ausente_apenas_avisa() -> None:
    async def factory(*args, **kwargs):
        raise FileNotFoundError("lms")

    before = _metric("missing")
    unloader = LmsCliUnloader(process_factory=factory)
    assert await unloader.unload_all() is False
    assert _metric("missing") == before + 1


@pytest.mark.unit
async def test_cli_com_erro_nao_derruba() -> None:
    async def factory(*args, **kwargs):
        return _Process(returncode=1, stderr=b"boom token=segredo")

    before = _metric("failed")
    unloader = LmsCliUnloader(process_factory=factory)
    assert await unloader.unload_all() is False
    assert _metric("failed") == before + 1


@pytest.mark.unit
async def test_timeout_mata_processo_e_nao_derruba() -> None:
    processes: list[_Process] = []

    async def factory(*args, **kwargs):
        process = _Process(hang=True)
        processes.append(process)
        return process

    before = _metric("timeout")
    unloader = LmsCliUnloader(timeout_seconds=0.01, process_factory=factory)
    assert await unloader.unload_all() is False
    assert processes[0].killed is True
    assert _metric("timeout") == before + 1


@pytest.mark.unit
@pytest.mark.skipif(os.name != "nt", reason="batch file e Windows-only")
async def test_executavel_falso_real_sucesso(tmp_path) -> None:
    script = tmp_path / "lms.bat"
    script.write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
    unloader = LmsCliUnloader(cli_path=str(script), timeout_seconds=5)
    assert await unloader.unload_all() is True


@pytest.mark.unit
@pytest.mark.skipif(os.name != "nt", reason="batch file e Windows-only")
async def test_executavel_falso_real_falha(tmp_path) -> None:
    script = tmp_path / "lms.bat"
    script.write_text("@echo off\r\nexit /b 7\r\n", encoding="ascii")
    unloader = LmsCliUnloader(cli_path=str(script), timeout_seconds=5)
    assert await unloader.unload_all() is False


@pytest.mark.unit
async def test_path_vazio_usa_lms_do_path() -> None:
    calls: list[tuple] = []

    async def factory(*args, **kwargs):
        calls.append(args)
        return _Process()

    unloader = LmsCliUnloader(cli_path="", process_factory=factory)
    await unloader.unload_all()
    assert calls[0][0] == "lms"
