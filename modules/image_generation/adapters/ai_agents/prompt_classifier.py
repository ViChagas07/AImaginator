"""Classificadores de topico de prompt (detalhe de infra do guardrail de escopo).

- StubPromptClassifier: determinista, para dev/testes/CI (sem chave real);
  passa o prompt adiante como relacionado a imagem (espelha StubImageProvider).
- HttpPromptClassifier: classificacao real via LLM leve/economico (Chat
  Completions), forca JSON estrito e devolve ClassificationResult.

Ambos implementam IPromptClassifier (definido em domain/prompt_topic_guard.py).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from modules.image_generation.domain.prompt_topic_guard import ClassificationResult

# System prompt do classificador: classifica e devolve APENAS JSON estrito
# (sem markdown, sem preambulo, sem texto livre).
TOPIC_CLASSIFIER_SYSTEM_PROMPT = """\
Você é um classificador de escopo do AImaginator. Sua única função é
decidir se um texto descreve uma intenção de GERAÇÃO ou EDIÇÃO de imagens.

Responda EXCLUSIVAMENTE com um objeto JSON válido, sem markdown, sem preâmbulo,
sem texto livre, no seguinte formato exato:

{"is_image_related": <true|false>, "cleaned_prompt": "<string|null>", "confidence": <0.0 a 1.0>}

Regras:
- is_image_related = true apenas se houver intenção clara de gerar ou editar uma imagem.
- cleaned_prompt: a parte do texto relacionada a imagem, reescrita de forma limpa;
  se não houver nada relevante, use null.
- confidence: sua confiança na decisão, de 0.0 (nada confiante) a 1.0 (certeza absoluta)."""

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class _ClassifierPayload(BaseModel):
    """Schema estrito da resposta do classificador (fail-fast no parsing)."""

    is_image_related: bool
    cleaned_prompt: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


def _parse_json(content: str) -> _ClassifierPayload:
    """Extrai JSON estrito (tolera fences markdown) e valida com Pydantic."""
    text = _FENCE_PATTERN.sub("", content).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Resposta do classificador nao e JSON valido: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Resposta do classificador nao e um objeto JSON.")
    return _ClassifierPayload.model_validate(data)


class StubPromptClassifier:
    """Classificador determinista: trata todo prompt como relacionado a imagem."""

    async def classify(self, prompt: str) -> ClassificationResult:
        return ClassificationResult(
            is_image_related=True, cleaned_prompt=prompt, confidence=1.0
        )


class HttpPromptClassifier:
    """Classificacao real via API externa (Chat Completions)."""

    def __init__(
        self,
        *,
        http_client: Any,
        api_base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        self._http = http_client
        self._base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def classify(self, prompt: str) -> ClassificationResult:
        response = await self._http.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": TOPIC_CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=5.0,
        )
        if response.status_code != 200:
            raise ValueError(f"Classificador respondeu HTTP {response.status_code}")

        try:
            content: str = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Resposta do classificador sem conteudo utilizavel.") from exc

        try:
            payload = _parse_json(content)
        except ValidationError as exc:
            raise ValueError(f"Resposta do classificador invalida: {exc}") from exc

        return ClassificationResult(
            is_image_related=payload.is_image_related,
            cleaned_prompt=payload.cleaned_prompt,
            confidence=payload.confidence,
        )


class GeminiPromptClassifier:
    """Classificação via API nativa do Gemini (Generative Language API).

    Diferente do HttpPromptClassifier (formato OpenAI Chat Completions),
    este usa o endpoint nativo do Gemini com autenticação via query param
    e payload/resposta no formato próprio do Gemini.
    """

    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        *,
        http_client: Any,
        api_key: str,
        model: str = "gemini-1.5-flash",
    ) -> None:
        self._http = http_client
        self._api_key = api_key
        # Normaliza o nome do modelo: aceita "gemini-1.5-flash" ou "models/gemini-1.5-flash"
        self._model = model.replace("models/", "")

    async def classify(self, prompt: str) -> ClassificationResult:
        url = f"{self._BASE_URL}/models/{self._model}:generateContent?key={self._api_key}"

        # Prompt completo (system + user) no formato Gemini
        full_prompt = f"{TOPIC_CLASSIFIER_SYSTEM_PROMPT}\n\nUsuário: {prompt}"

        response = await self._http.post(
            url,
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": full_prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 512,
                    "responseMimeType": "application/json",
                },
            },
            timeout=10.0,
        )

        if response.status_code != 200:
            # Tenta extrair erro do corpo da resposta
            try:
                err = response.json()
                raise ValueError(f"Gemini API erro HTTP {response.status_code}: {err}")
            except Exception:
                raise ValueError(f"Gemini API erro HTTP {response.status_code}")

        try:
            # Resposta Gemini: candidates[0].content.parts[0].text
            candidates = response.json()["candidates"]
            if not candidates:
                raise ValueError("Resposta do Gemini sem candidates")
            content: str = candidates[0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Resposta do Gemini sem conteúdo utilizável.") from exc

        try:
            payload = _parse_json(content)
        except ValidationError as exc:
            raise ValueError(f"Resposta do classificador Gemini inválida: {exc}") from exc

        return ClassificationResult(
            is_image_related=payload.is_image_related,
            cleaned_prompt=payload.cleaned_prompt,
            confidence=payload.confidence,
        )
