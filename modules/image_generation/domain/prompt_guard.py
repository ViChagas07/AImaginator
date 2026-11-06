"""Guarda anti prompt-injection (camada domain — regra de negocio de seguranca).

Defesa em profundidade (spec secao 7):
1. Esta guarda valida/sanitiza ANTES de qualquer prompt chegar ao agente.
2. O adapter de agentes usa delimitadores estruturados ao montar prompts
   de sistema (nunca concatena input do usuario diretamente).
3. A resposta do agente e validada por schema antes de ser usada.

A normalizacao remove caracteres invisiveis/controle e colapsa espacos; para
DETECCAO, aplica tambem um leetspeak basico. O texto devolvido preserva a
escrita do usuario (apenas normalizada), sem "corrigir" o conteudo.
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
        # EN
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
        # PT
        r"ignore\s+(todas\s+)?(as\s+)?instru[cç][oõ]es\s+anteriores",
        r"ignore\s+(todas\s+)?(as\s+)?regras\s+anteriores",
        r"esque[cç]a\s+(todas\s+)?(as\s+)?instru[cç][oõ]es",
        r"revele\s+(o\s+)?(seu\s+)?prompt\s+do\s+sistema",
        r"modo\s+desenvolvedor",
        # ES
        r"ignora\s+(todas\s+)?(las\s+)?instrucciones\s+anteriores",
        r"olvida\s+(todas\s+)?(las\s+)?instrucciones",
        r"revela\s+(el\s+)?prompt\s+del\s+sistema",
        # FR
        r"ignore[zr]?\s+(toutes\s+)?(les\s+)?instructions\s+pr[eé]c[eé]dentes",
        r"oublie[zr]?\s+(toutes\s+)?(les\s+)?instructions",
        r"r[eé]v[eè]le[zr]?\s+(le\s+)?prompt\s+syst[eè]me",
        # DE
        r"ignoriere\s+(alle\s+)?(vorherigen\s+)?anweisungen",
        r"vergiss\s+(alle\s+)?(vorherigen\s+)?anweisungen",
        r"zeige\s+(den\s+)?system\s*prompt",
        # IT
        r"ignora\s+(tutte\s+)?(le\s+)?istruzioni\s+precedenti",
        r"dimentica\s+(tutte\s+)?(le\s+)?istruzioni",
        r"rivela\s+(il\s+)?prompt\s+di\s+sistema",
        # JA
        r"以前の指示を無視",
        r"すべての指示を忘れ",
        r"システムプロンプトを(開示|表示|教えて)",
        # ZH
        r"忽略(所有)?(之前|先前)的(指令|指示)",
        r"忘记(所有)?(之前|先前)的(指令|指示)",
        r"显示(你的)?系统提示",
        # KO
        r"이전\s*(지시|명령)을?\s*무시",
        r"모든\s*(지시|명령)을?\s*잊어",
        r"시스템\s*프롬프트를?\s*(보여|공개)",
        # RU
        r"игнорируй\s+(все\s+)?(предыдущие\s+)?инструкции",
        r"забудь\s+(все\s+)?(предыдущие\s+)?инструкции",
        r"покажи\s+(системный\s+)?промпт",
        # AR
        r"تجاهل\s+(كل\s+)?(ال)?تعليمات\s+(ال)?سابقة",
        r"انسَ\s+(كل\s+)?(ال)?تعليمات",
        r"أظهر\s+(ال)?برومبت\s+(ال)?نظام",
    )
)

# Separadores de fronteira usados por agentes para delimitar contexto.
_DELIMITER_PATTERN = re.compile(r"(<{3,}|>{3,}|`{3,}|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>)")
_LEET_MAP = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
    }
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


class PromptInjectionGuard:
    """Valida e sanitiza prompts do usuario (servico de dominio puro)."""

    def __init__(self, *, max_length: int = MAX_PROMPT_LENGTH) -> None:
        self._max_length = max_length

    def validate(self, raw_prompt: str) -> str:
        """Devolve o prompt sanitizado ou levanta PromptInjectionDetectedError."""
        prompt = self._sanitize(raw_prompt)

        if not (MIN_PROMPT_LENGTH <= len(prompt) <= self._max_length):
            msg = f"Prompt deve ter entre {MIN_PROMPT_LENGTH} e {self._max_length} caracteres."
            raise PromptInjectionDetectedError(msg)

        detection = self._detection_form(prompt)
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(detection):
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
        """NFKC, remove controles/zero-width e colapsa espacos."""
        normalized = unicodedata.normalize("NFKC", raw)
        cleaned = "".join(
            ch
            for ch in normalized
            if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
        )
        return _WHITESPACE_PATTERN.sub(" ", cleaned).strip()

    @staticmethod
    def _detection_form(prompt: str) -> str:
        """Leetspeak basico apenas para deteccao; nao altera o prompt salvo."""
        lowered = prompt.lower().translate(_LEET_MAP)
        return unicodedata.normalize("NFKC", lowered)
