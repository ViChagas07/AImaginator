"""Smoke test MANUAL do assistente real (LM Studio/Qwen). NAO rode em CI.

Uso:
    python tools/smoke_assistant.py
    python tools/smoke_assistant.py --repeat 2

O script envia um caso por vez, imprime latencia (primeira chamada inclusa) e
a decisao/reescrita. Feche outros programas pesados e monitore a RAM.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from infra.settings import get_settings  # noqa: E402
from modules.image_generation.adapters.ai_agents.llm_client import (  # noqa: E402
    OpenAICompatibleLlmClient,
)
from modules.image_generation.application.services.prompt_assistant import (  # noqa: E402
    PromptAssistant,
)
from modules.image_generation.domain.entities import GenerationKind  # noqa: E402
from modules.image_generation.domain.prompt_assistant import AssistantInput  # noqa: E402
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard  # noqa: E402
from shared_kernel.security_errors import PromptInjectionDetectedError  # noqa: E402
from specs.evals.prompt_assistant_eval import CASES  # noqa: E402


def _print_warning() -> None:
    print("=" * 72)
    print("SMOKE TEST MANUAL DO ASSISTENTE (LM Studio/Qwen real)")
    print("Feche programas pesados e monitore RAM/temperatura.")
    print("Uma etapa por vez; interrompa em caso de throttle ou desligamento.")
    print("=" * 72)


async def _run(limit: int) -> int:
    settings = get_settings()
    guard = PromptInjectionGuard()
    async with httpx.AsyncClient() as http:
        llm = OpenAICompatibleLlmClient(
            http_client=http,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
            ttl_seconds=settings.llm_ttl_seconds,
        )
        assistant = PromptAssistant(
            llm=llm, block_confidence=settings.llm_block_confidence
        )
        latencies: list[float] = []
        for index, (locale, text, expected) in enumerate(CASES[:limit], start=1):
            started = time.perf_counter()
            try:
                guard.validate(text)
            except PromptInjectionDetectedError:
                print(
                    f"[{index:02d}] {locale} injection | esperado={expected} | "
                    f"guard={time.perf_counter() - started:.2f}s"
                )
                continue
            try:
                result = await assistant.analyze(
                    AssistantInput(
                        text=text, kind=GenerationKind.GENERATE, locale=locale
                    )
                )
            except Exception as exc:
                print(
                    f"[{index:02d}] {locale} ERRO {type(exc).__name__} | "
                    f"esperado={expected} | {time.perf_counter() - started:.2f}s"
                )
                continue
            elapsed = time.perf_counter() - started
            latencies.append(elapsed)
            code = result.refusal_code(block_confidence=settings.llm_block_confidence)
            rewrite = (
                result.flux_prompt
                or result.kontext_instruction
                or result.corrected_text
                or ""
            )
            print(
                f"[{index:02d}] {locale} esperado={expected} obtido={code or 'pass'}"
                f" conf={result.confidence:.2f} lang={result.detected_language}"
                f" | {elapsed:.2f}s"
            )
            if rewrite:
                print(f"     rewrite: {rewrite}")
        if latencies:
            first = latencies[0]
            rest = latencies[1:]
            average = sum(rest) / len(rest) if rest else 0.0
            print(
                f"\nLatencia: primeira={first:.2f}s "
                f"media_seguintes={average:.2f}s ({len(rest)} chamadas)"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke manual do assistente")
    parser.add_argument("--limit", type=int, default=len(CASES))
    args = parser.parse_args()
    _print_warning()
    return asyncio.run(_run(max(1, min(args.limit, len(CASES)))))


if __name__ == "__main__":
    raise SystemExit(main())
