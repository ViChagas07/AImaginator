"""Guarda anti prompt-injection (camada domain — regra de negocio de seguranca).

Defesa em profundidade (spec secao 7):
1. Esta guarda valida/sanitiza ANTES de qualquer prompt chegar ao agente.
2. O adapter de agentes usa delimitadores estruturados ao montar prompts
   de sistema (nunca concatena input do usuario diretamente).
3. A resposta do agente e validada por schema antes de ser usada.
"""

from __future__ import annotations

import re
import unicodedata

from shared_kernel.security_errors import PromptInjectionDetectedError

MAX_PROMPT_LENGTH = 2000
MIN_PROMPT_LENGTH = 1

# Padroes classicos de tentativa de injecao/sobreescrita de instrucoes.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE | re.UNICODE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"forget\s+(everything|all|your\s+instructions?)",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"act\s+as\s+(a|an)\s+(new|different|evil|unrestricted)",
        r"system\s*prompt",
        r"\bDAN\b.*\bmode\b",
        r"jailbreak",
        r"reveal\s+(your|the)\s+(instructions?|system\s*prompt|rules?)",
        r"override\s+(safety|filters?|guardrails?)",
        r"\bdo\s+anything\s+now\b",
    )
)

# Separadores de fronteira usados por agentes para delimitar contexto.
_DELIMITER_PATTERN = re.compile(r"(<{3,}|>{3,}|`{3,}|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>)")


class PromptInjectionGuard:
    """Valida e sanitiza prompts do usuario (servico de dominio puro)."""

    def validate(self, raw_prompt: str) -> str:
        """Devolve o prompt sanitizado ou levanta PromptInjectionDetectedError."""
        prompt = self._sanitize(raw_prompt)

        if not (MIN_PROMPT_LENGTH <= len(prompt) <= MAX_PROMPT_LENGTH):
            msg = f"Prompt deve ter entre {MIN_PROMPT_LENGTH} e {MAX_PROMPT_LENGTH} caracteres."
            raise PromptInjectionDetectedError(msg)

        for pattern in _INJECTION_PATTERNS:
            if pattern.search(prompt):
                raise PromptInjectionDetectedError(
                    "Prompt contem padrao de manipulacao de instrucoes."
                )
        if _DELIMITER_PATTERN.search(prompt):
            raise PromptInjectionDetectedError(
                "Prompt contem delimitadores reservados ao sistema."
            )
        return prompt

    @staticmethod
    def _sanitize(raw: str) -> str:
        """Normaliza unicode, remove controles nao imprimiveis, colapsa espacos."""
        normalized = unicodedata.normalize("NFKC", raw)
        cleaned = "".join(
            ch for ch in normalized if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
        )
        return cleaned.strip()
