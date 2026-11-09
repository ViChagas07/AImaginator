"""Descarregamento explicito do LM Studio via `lms unload --all`.

O `ttl` do request nao vale para modelos carregados manualmente. Rodamos o
CLI em subprocesso SEM shell, com timeout curto; qualquer falha e apenas
aviso + metrica (o job nunca morre por isso).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import Any

from modules.observability.logging_config import get_logger
from modules.observability.metrics import LLM_UNLOAD_TOTAL
from modules.observability.sentry_setup import scrub_text

logger = get_logger(__name__)

_PREVIEW_CHARS = 500


def _safe_log_text(value: str) -> str:
    return value.encode("ascii", "backslashreplace").decode("ascii")


class LmsCliUnloader:
    def __init__(
        self,
        *,
        cli_path: str = "",
        timeout_seconds: float = 20.0,
        process_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._cli_path = cli_path.strip() or "lms"
        self._timeout = timeout_seconds
        self._process_factory = process_factory or asyncio.create_subprocess_exec

    async def unload_all(self) -> bool:
        started = time.perf_counter()
        try:
            process = await self._process_factory(
                self._cli_path,
                "unload",
                "--all",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            LLM_UNLOAD_TOTAL.labels(outcome="missing").inc()
            logger.warning(
                "llm_unload_failed",
                branch="missing_cli",
                cli=self._cli_path,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            return False
        except Exception as exc:
            LLM_UNLOAD_TOTAL.labels(outcome="failed").inc()
            logger.warning(
                "llm_unload_failed",
                branch="spawn",
                cli=self._cli_path,
                error_type=type(exc).__name__,
                error_message=_safe_log_text(str(exc))[:_PREVIEW_CHARS],
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            return False

        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        except TimeoutError:
            with contextlib.suppress(Exception):
                process.kill()
                await process.wait()
            LLM_UNLOAD_TOTAL.labels(outcome="timeout").inc()
            logger.warning(
                "llm_unload_failed",
                branch="timeout",
                cli=self._cli_path,
                timeout_seconds=self._timeout,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            return False
        except Exception as exc:
            LLM_UNLOAD_TOTAL.labels(outcome="failed").inc()
            logger.warning(
                "llm_unload_failed",
                branch="communicate",
                cli=self._cli_path,
                error_type=type(exc).__name__,
                error_message=_safe_log_text(str(exc))[:_PREVIEW_CHARS],
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            return False

        returncode = getattr(process, "returncode", None)
        if returncode not in (0, None):
            error_text = b""
            if isinstance(stderr, bytes | bytearray):
                error_text = bytes(stderr)
            LLM_UNLOAD_TOTAL.labels(outcome="failed").inc()
            logger.warning(
                "llm_unload_failed",
                branch="nonzero_exit",
                cli=self._cli_path,
                returncode=returncode,
                stderr=_safe_log_text(scrub_text(error_text.decode("utf-8", errors="replace")))[
                    :_PREVIEW_CHARS
                ],
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            return False

        LLM_UNLOAD_TOTAL.labels(outcome="success").inc()
        logger.info(
            "llm_unloaded",
            cli=self._cli_path,
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )
        return True
