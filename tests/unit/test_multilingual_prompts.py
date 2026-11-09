"""Prompts sao aceitos em qualquer idioma, independente do locale do site."""

from __future__ import annotations

import pytest

from modules.image_generation.application.guardrails import check_scope_localized
from modules.image_generation.application.services.prompt_assistant import (
    ASSISTANT_SYSTEM_PROMPT,
    PromptAssistant,
)
from modules.image_generation.domain.entities import GenerationKind
from modules.image_generation.domain.prompt_assistant import AssistantInput
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.scope_guard import ScopeGuardrail
from tests.fakes.llm import FakeLlmClient, assistant_json


@pytest.mark.unit
@pytest.mark.parametrize(
    "prompt",
    [
        "crie uma imagem de uma cabana na floresta à noite",
        "create an image of a cabin in the forest at night",
        "crea una imagen de una cabaña en el bosque de noche",
        "夜の森にある小さな小屋の画像を作って",
        "أنشئ صورة لكوخ في غابة ليلاً",
        "bild eines hütte im wald bei nacht",
    ],
)
def test_guardas_aceitam_intencao_de_imagem_em_varios_idiomas(prompt: str) -> None:
    cleaned = PromptInjectionGuard().validate(prompt)
    ScopeGuardrail().check(cleaned)
    check_scope_localized(ScopeGuardrail(), cleaned, "pt-BR")


@pytest.mark.unit
async def test_site_pt_br_com_prompt_estrangeiro_usa_flux_prompt_em_ingles() -> None:
    assistant = PromptAssistant(
        llm=FakeLlmClient(
            [
                assistant_json(
                    detected_language="ja",
                    corrected_text="夜の森にある小さな小屋",
                    flux_prompt="a small cabin in a forest at night",
                )
            ]
        )
    )
    result = await assistant.analyze(
        AssistantInput(
            text="夜の森にある小さな小屋の画像を作って",
            kind=GenerationKind.GENERATE,
            locale="pt-BR",
        )
    )

    assert result.detected_language == "ja"
    assert result.engine_prompt(GenerationKind.GENERATE) == (
        "a small cabin in a forest at night"
    )


@pytest.mark.unit
def test_contrato_do_assistente_exige_flux_prompt_em_ingles() -> None:
    assert "flux_prompt must be a faithful, natural ENGLISH" in ASSISTANT_SYSTEM_PROMPT
    assert "detected_language" in ASSISTANT_SYSTEM_PROMPT
