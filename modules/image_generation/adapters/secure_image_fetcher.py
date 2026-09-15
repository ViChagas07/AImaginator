"""Fetcher HTTP de imagens externas com segunda linha de defesa anti-SSRF.

A primeira linha (UrlPolicy no domain) valida scheme/allowlist/literal
de IP ANTES do request. Aqui, no momento do fetch:
- resolvemos o DNS e rejeitamos IPs privados/loopback/link-local
  (previne DNS rebinding para rede interna);
- nao seguimos redirects automaticamente (cada redirect seria uma nova
  URL nao validada — preferimos rejeitar);
- limitamos bytes lidos (anti buffer overflow, spec secao 7).
"""

from __future__ import annotations

import base64
import ipaddress
import socket

import httpx

from modules.image_generation.application.ports import ImageFetcherPort
from modules.image_generation.domain.url_policy import UrlPolicy
from shared_kernel.errors import DomainError
from shared_kernel.security_errors import SSRFBlockedError

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


class SecureImageFetcher(ImageFetcherPort):
    def __init__(self, *, url_policy: UrlPolicy, http_client: httpx.AsyncClient) -> None:
        self._policy = url_policy
        self._http = http_client

    async def fetch(self, url: str) -> bytes:
        self._policy.validate(url)
        await self._validate_dns(url)

        async with self._http.stream(
            "GET", url, follow_redirects=False, timeout=15
        ) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                raise SSRFBlockedError("Redirects externos nao sao seguidos por seguranca.")
            if response.status_code != 200:
                raise DomainError(f"Falha ao baixar imagem (HTTP {response.status_code}).")
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise DomainError("URL nao aponta para uma imagem valida.")

            chunks = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                chunks.extend(chunk)
                if len(chunks) > _MAX_IMAGE_BYTES:
                    raise DomainError("Imagem excede o tamanho maximo permitido (10 MB).")
        return bytes(chunks)

    async def fetch_base64_data_url(self, url: str) -> str:
        data = await self.fetch(url)
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"

    @staticmethod
    async def _validate_dns(url: str) -> None:
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise SSRFBlockedError(f"DNS do host nao resolveu: {host}") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise SSRFBlockedError("DNS resolveu para IP interno/reservado.")
