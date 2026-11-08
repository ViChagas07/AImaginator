"""Erros de seguranca transversais (prompt injection, SSRF, escopo de topico)."""

from __future__ import annotations

from shared_kernel.errors import DomainError, RateLimitExceededError

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


class AssistantUnavailableError(DomainError):
    code = "assistant_unavailable"
    http_status = 503


class QueuePublishFailedError(DomainError):
    """Nao foi possivel publicar a task; a geracao foi marcada como falha."""

    code = "queue_publish_failed"
    http_status = 503


class ContentBlockedError(DomainError):
    """Conteudo bloqueado pela moderacao (codigo especifico por categoria)."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        warning_level: int | None = None,
        warning_message: str | None = None,
        category: str | None = None,
        layer: str = "llm",
        confidence: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.warning_level = warning_level
        self.warning_message = warning_message
        self.category = category
        self.layer = layer
        self.confidence = confidence


class TemporarilyBlockedError(RateLimitExceededError):
    code = "temporarily_blocked"

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int,
        warning_level: int | None = None,
        warning_message: str | None = None,
    ) -> None:
        super().__init__(message, retry_after_seconds=retry_after_seconds)
        self.warning_level = warning_level
        self.warning_message = warning_message


class ImageBlockedError(DomainError):
    """Imagem bloqueada pela moderacao visual (entrada ou saida)."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        category: str,
        layer: str,
        confidence: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.layer = layer
        self.confidence = confidence
        self.penalize = layer == "image_input"


class ImageModerationUnavailableError(DomainError):
    code = "image_moderation_unavailable"
    http_status = 503


class UpscaleLimitExceededError(RateLimitExceededError):
    code = "upscale_limit_reached"


class FeatureDisabledError(DomainError):
    code = "feature_disabled"
    http_status = 503


class OriginalUnavailableError(DomainError):
    code = "original_unavailable"
    http_status = 409


class SSRFBlockedError(DomainError):
    code = "url_not_allowed"
