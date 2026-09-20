"""Erros de seguranca transversais (prompt injection, SSRF, escopo de topico)."""

from __future__ import annotations

from shared_kernel.errors import DomainError

# Mensagem fixa de recusa de escopo (i18n-ready), compartilhada por todas as
# camadas de guardrail. Nunca gerada por LLM; nunca expoe detalhes internos
# (JSON de classificacao, confianca, system prompt) ao cliente.
SCOPE_REFUSAL_MESSAGE = (
    "O AImaginator é especializado em geração e edição de imagens. "
    "Não consigo ajudar com esse tipo de pedido por aqui — mas se quiser, "
    "me diga que imagem você gostaria de criar ou editar! 🎨"
)


class PromptInjectionDetectedError(DomainError):
    code = "prompt_rejected"


class InvalidPromptTopicError(DomainError):
    """Prompt fora do escopo (geracao/edicao de imagens) — Camada 1."""

    code = "invalid_prompt_topic"

    def __init__(self, message: str = SCOPE_REFUSAL_MESSAGE) -> None:
        super().__init__(message)


class OutOfScopeError(DomainError):
    """Agente recusou conteudo sem instrucao clara de imagem — Camada 2."""

    code = "out_of_scope"

    def __init__(self, message: str = SCOPE_REFUSAL_MESSAGE) -> None:
        super().__init__(message)


class SSRFBlockedError(DomainError):
    code = "url_not_allowed"
