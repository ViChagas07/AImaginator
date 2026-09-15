"""Erros de seguranca transversais (prompt injection, SSRF)."""

from __future__ import annotations

from shared_kernel.errors import DomainError


class PromptInjectionDetectedError(DomainError):
    code = "prompt_rejected"


class SSRFBlockedError(DomainError):
    code = "url_not_allowed"
