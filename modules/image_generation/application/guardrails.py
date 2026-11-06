"""Adaptadores de mensagens localizadas para as guardas deterministicas.

As guardas de dominio continuam puras (sem conhecer locale); a aplicacao
traduz o erro para o idioma do SITE no momento da requisicao.
"""

from __future__ import annotations

from modules.image_generation.application.localization import message_for
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.scope_guard import ScopeGuardrail
from modules.observability.metrics import REFUSALS_TOTAL
from shared_kernel.security_errors import OutOfScopeError, PromptInjectionDetectedError


def validate_prompt_localized(
    guard: PromptInjectionGuard, text: str, locale: str
) -> str:
    try:
        return guard.validate(text)
    except PromptInjectionDetectedError as exc:
        REFUSALS_TOTAL.labels(code="prompt_rejected").inc()
        raise PromptInjectionDetectedError(
            message_for("prompt_rejected", locale)
        ) from exc


def check_scope_localized(
    guard: ScopeGuardrail, prompt: str, locale: str
) -> None:
    try:
        guard.check(prompt)
    except OutOfScopeError as exc:
        REFUSALS_TOTAL.labels(code="out_of_scope").inc()
        raise OutOfScopeError(message_for("out_of_scope", locale)) from exc
