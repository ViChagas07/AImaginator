"""Politica de URL externa (anti-SSRF, camada domain — pura).

Primeira linha de defesa (validacao sincrona no request):
- apenas HTTPS;
- dominio precisa estar na allowlist de settings;
- literais de IP e nomes internos (localhost, metadata cloud) sao
  recusados antes mesmo do DNS.

Segunda linha (no adapter de fetch): resolucao de DNS validada — o IP
resolvido nao pode ser privado/loopback/link-local — e redirect nao e
seguido cegamente.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from shared_kernel.security_errors import SSRFBlockedError

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "instance-data",
        "169.254.169.254",  # metadata AWS/GCP
    }
)


class UrlPolicy:
    def __init__(self, allowed_domains: frozenset[str]) -> None:
        self._allowed = {d.lower() for d in allowed_domains}

    def validate(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise SSRFBlockedError("Apenas URLs HTTPS sao permitidas.")
        host = (parsed.hostname or "").lower()
        if not host:
            raise SSRFBlockedError("URL sem host valido.")
        if host in _BLOCKED_HOSTNAMES:
            raise SSRFBlockedError("Host interno nao permitido.")
        if self._is_ip_literal(host):
            raise SSRFBlockedError("Literais de IP nao sao permitidos.")
        if not any(host == d or host.endswith(f".{d}") for d in self._allowed):
            raise SSRFBlockedError(f"Dominio '{host}' fora da allowlist.")
        return url

    @staticmethod
    def _is_ip_literal(host: str) -> bool:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True
