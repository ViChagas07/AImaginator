"""Erros base compartilhados do AImaginator (shared_kernel — manter minimo)."""

from __future__ import annotations


class AImaginatorError(Exception):
    """Erro base de toda a aplicacao."""

    code: str = "internal_error"
    http_status: int = 500

    def __init__(self, message: str | None = None, *, details: dict | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details or {}


class DomainError(AImaginatorError):
    """Violacao de regra de negocio (camada domain/application)."""

    code = "domain_error"
    http_status = 422


class NotFoundError(AImaginatorError):
    code = "not_found"
    http_status = 404


class UnauthorizedError(AImaginatorError):
    code = "unauthorized"
    http_status = 401


class ForbiddenError(AImaginatorError):
    code = "forbidden"
    http_status = 403


class ConflictError(AImaginatorError):
    code = "conflict"
    http_status = 409


class PayloadTooLargeError(AImaginatorError):
    code = "payload_too_large"
    http_status = 413


class RateLimitExceededError(AImaginatorError):
    code = "rate_limit_exceeded"
    http_status = 429

    def __init__(
        self,
        message: str = "Muitas requisicoes. Tente novamente em instantes.",
        *,
        retry_after_seconds: int = 60,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after_seconds = retry_after_seconds


class QuotaExceededError(AImaginatorError):
    code = "quota_exceeded"
    http_status = 429

    def __init__(
        self,
        message: str = "Cota de prompts esgotada.",
        *,
        retry_after_seconds: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after_seconds = retry_after_seconds


class CircuitOpenError(AImaginatorError):
    """Circuit breaker aberto: dependencia externa indisponivel, falha rapida."""

    code = "service_unavailable"
    http_status = 503
