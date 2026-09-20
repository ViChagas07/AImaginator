"""Guarda de escopo de topico (camada domain — regra de negocio).

Camada 1 da defesa em profundidade (independente do PromptInjectionGuard):
garante que apenas prompts sobre geracao/edicao de imagens sigam para o
pipeline. A classificacao semanticamente robusta (prompts mistos, etc.)
e delegada a um classificador via LLM leve atraves da abstracao
IPromptClassifier — nunca regex inline, que nao separa com confiabilidade a
parte de imagem de pedidos fora de escopo sem falsos positivos/negativos.

Executa APOS o PromptInjectionGuard: a guarda de injecao e mais barata e
barra tentativas obvias antes de gastar uma chamada de LLM aqui.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from shared_kernel.security_errors import InvalidPromptTopicError

# Threshold de confianca minima exigida do classificador para aceitar o prompt.
MIN_CONFIDENCE = 0.6
# Timeout (segundos) da chamada ao classificador. Dentro da faixa 3-5s exigida;
# estouro => fail-closed.
CLASSIFIER_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Resultado estruturado devolvido pelo classificador de topico."""

    is_image_related: bool
    cleaned_prompt: str | None
    confidence: float


class IPromptClassifier(Protocol):
    """Porta do classificador de topico (troca de provedor sem tocar a regra)."""

    async def classify(self, prompt: str) -> ClassificationResult:
        """Classifica o prompt e devolve a parte relacionada a imagem."""
        ...


class IPromptTopicGuard(Protocol):
    """Porta da guarda de escopo — unica superficie usada pelos use cases."""

    async def validate(self, prompt: str) -> str:
        """Devolve o prompt limpo (so a parte de imagem) ou levanta erro."""
        ...


class PromptTopicGuard:
    """Valida se o prompt do usuario e sobre geracao/edicao de imagens."""

    def __init__(
        self,
        classifier: IPromptClassifier,
        *,
        min_confidence: float = MIN_CONFIDENCE,
        timeout_seconds: float = CLASSIFIER_TIMEOUT_SECONDS,
    ) -> None:
        self._classifier = classifier
        self._min_confidence = min_confidence
        self._timeout_seconds = timeout_seconds

    async def validate(self, prompt: str) -> str:
        """Retorna o cleaned_prompt (so a parte de imagem) ou levanta erro.

        Fail-closed: qualquer falha de parsing, timeout ou resultado sem
        relacao clara com imagem rejeita o prompt (nunca deixa passar).
        """
        try:
            result = await asyncio.wait_for(
                self._classifier.classify(prompt), timeout=self._timeout_seconds
            )
        except TimeoutError as exc:
            raise InvalidPromptTopicError() from exc
        except Exception as exc:
            # Parsing malformado ou erro de infraestrutura do classificador:
            # falha fechada, nao arrisca processar conteudo fora de escopo.
            raise InvalidPromptTopicError() from exc

        cleaned = (result.cleaned_prompt or "").strip()
        if (
            not result.is_image_related
            or result.confidence < self._min_confidence
            or not cleaned
        ):
            raise InvalidPromptTopicError()
        return cleaned
