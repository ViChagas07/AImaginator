"""Guarda deterministica de escopo (primeira camada, sem LLM).

Recusa apenas pedidos claramente textuais/analiticos que nao tenham nenhum
sinal de intencao de imagem. A camada semantica final (assistente) roda no
worker; esta guarda existe para resposta rapida e defesa em profundidade.
"""

from __future__ import annotations

import re

from shared_kernel.security_errors import OutOfScopeError

_IMAGE_SCOPE_SIGNALS = (
    r"\bimagem\b",
    r"\bimage\b",
    r"\bfoto\b",
    r"\bfotografia\b",
    r"\bphoto\b",
    r"\bpicture\b",
    r"\bdesenh(?:ar|o)\b",
    r"\bdraw(?:ing)?\b",
    r"\bpint(?:ar|ura|ing)\b",
    r"\bpaint(?:ing)?\b",
    r"\bilustr(?:ar|acao)\b",
    r"\billustrat(?:e|ion)\b",
    r"\brender(?:izar)?\b",
    r"\bger(?:ar|acao)\b",
    r"\bgenerat(?:e|ion)\b",
    r"\bcri(?:ar|acao)\b",
    r"\bcreat(?:e|ion)\b",
    r"\bedit\w*\b",
    r"\bretrato\b",
    r"\bportrait\b",
    r"\bcenario\b",
    r"\bscene\b",
    r"\bcomposicao\b",
    r"\bcomposition\b",
    r"\baquarela\b",
    r"\bwatercolor\b",
    r"\boleo\b",
    r"\boil\b",
    r"\bcyberpunk\b",
    r"\banime\b",
    r"\bfotorrealist\w*\b",
    r"\bphotorealistic\b",
    r"\bestilo\b",
    r"\bstyle\b",
    r"\barte\b",
    r"\bart\b",
    r"\bcanvas\b",
    r"\btela\b",
)

_OUT_OF_SCOPE_SIGNALS = (
    r"\bexpli[qc]\w*\b",
    r"\bexplain\w*\b",
    r"\bescrev\w*\b",
    r"\bwrite\b",
    r"\bredi[gj]\w*\b",
    r"\btraduz\w*\b",
    r"\btranslat\w*\b",
    r"\bresum\w*\b",
    r"\bsummari[sz]e\b",
    r"\bpoema\b",
    r"\bpoem\b",
    r"\bensai\w*\b",
    r"\bessay\b",
    r"\bartigo\b",
    r"\barticle\b",
    r"\b(?:e-?mail|email)\b",
    r"\bc[óo]digo\b",
    r"\bcode\b",
    r"\bscript\b",
    r"\bfun[çc][ãa]o\b",
    r"\bfunction\b",
    r"\bpergunta\b",
    r"\bquestion\b",
    r"\brespond\w*\b",
    r"\banswer\b",
    r"\bcalcul\w*\b",
    r"\bsolve\b",
    r"\bresolv\w*\b",
    r"\bpiada\b",
    r"\bjoke\b",
    r"\breceita\b",
    r"\brecipe\b",
    r"\bconselho\b",
    r"\badvice\b",
    r"\brelat[óo]rio\b",
    r"\breport\b",
)


class ScopeGuardrail:
    """Recusa pedidos textuais sem qualquer sinal de imagem."""

    def __init__(
        self,
        *,
        out_of_scope_signals: tuple[str, ...] = _OUT_OF_SCOPE_SIGNALS,
        image_signals: tuple[str, ...] = _IMAGE_SCOPE_SIGNALS,
    ) -> None:
        self._out_of_scope = tuple(
            re.compile(s, re.IGNORECASE | re.UNICODE) for s in out_of_scope_signals
        )
        self._image = tuple(
            re.compile(s, re.IGNORECASE | re.UNICODE) for s in image_signals
        )

    def check(self, prompt: str) -> None:
        has_image = any(p.search(prompt) for p in self._image)
        has_out_of_scope = any(p.search(prompt) for p in self._out_of_scope)
        if has_out_of_scope and not has_image:
            raise OutOfScopeError()
