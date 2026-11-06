"""Erros de dominio do motor de imagem (mensagens seguras para o usuario).

Os adapters registram o log completo internamente; a excecao carrega apenas
uma mensagem segura, sem caminhos locais, comandos ou saida bruta do runtime.
"""

from __future__ import annotations

from shared_kernel.errors import DomainError


class EngineError(DomainError):
    """Falha generica e segura do motor de imagem."""

    code = "engine_failed"
    http_status = 502

    def __init__(self, message: str = "Falha ao processar a imagem.") -> None:
        super().__init__(message)


class EngineTimeoutError(EngineError):
    code = "engine_timeout"

    def __init__(self, message: str = "O processamento excedeu o tempo limite.") -> None:
        super().__init__(message)


class EngineOutOfMemoryError(EngineError):
    code = "engine_oom"

    def __init__(self, message: str = "Memoria insuficiente para processar a imagem.") -> None:
        super().__init__(message)


class EngineFailedError(EngineError):
    code = "engine_failed"

    def __init__(self, message: str = "Falha ao processar a imagem.") -> None:
        super().__init__(message)


class InsufficientResourcesError(EngineError):
    code = "insufficient_resources"
    http_status = 503

    def __init__(
        self, message: str = "Recursos insuficientes no momento. Tente novamente mais tarde."
    ) -> None:
        super().__init__(message)


class InvalidImageDimensionsError(EngineError):
    code = "invalid_dimensions"
    http_status = 422

    def __init__(self, message: str = "Dimensao de imagem nao suportada.") -> None:
        super().__init__(message)
