"""Testes da politica anti-SSRF (UrlPolicy)."""

from __future__ import annotations

import pytest

from modules.image_generation.domain.url_policy import UrlPolicy
from shared_kernel.security_errors import SSRFBlockedError

policy = UrlPolicy(frozenset({"images.unsplash.com", "cdn.aimaginator.com"}))

BLOCKED = [
    "http://images.unsplash.com/foto.jpg",            # sem HTTPS
    "https://localhost/internal",                     # localhost
    "https://127.0.0.1/admin",                        # loopback literal
    "https://169.254.169.254/latest/meta-data/",      # metadata cloud
    "https://[::1]/",                                 # IPv6 loopback
    "https://evil.example.com/steal",                 # fora da allowlist
    "https://images.unsplash.com.evil.com/f.jpg",     # suffix spoofing
    "ftp://images.unsplash.com/f.jpg",                # scheme errado
]

ALLOWED = [
    "https://images.unsplash.com/photo-123",
    "https://cdn.aimaginator.com/gen/abc.png",
    "https://sub.images.unsplash.com/ok.jpg",         # subdominio permitido
]


@pytest.mark.unit
@pytest.mark.parametrize("url", BLOCKED)
def test_bloqueia_urls_maliciosas(url: str) -> None:
    with pytest.raises(SSRFBlockedError):
        policy.validate(url)


@pytest.mark.unit
@pytest.mark.parametrize("url", ALLOWED)
def test_permite_urls_da_allowlist(url: str) -> None:
    assert policy.validate(url) == url
