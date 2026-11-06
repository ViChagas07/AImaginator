"""Scrubbing do Sentry: prompt, e-mail, IP, tokens e URLs assinadas."""

from __future__ import annotations

import pytest

from modules.observability.sentry_setup import _scrub_event, scrub_text


@pytest.mark.unit
def test_scrub_text_remove_email_ip_token_e_url_assinada() -> None:
    text = (
        "user@example.com 10.1.2.3 Bearer abc.def.ghi "
        "https://bucket/x?X-Amz-Signature=deadbeef"
    )
    scrubbed = scrub_text(text)
    assert "user@example.com" not in scrubbed
    assert "10.1.2.3" not in scrubbed
    assert "abc.def.ghi" not in scrubbed
    assert "deadbeef" not in scrubbed


@pytest.mark.unit
def test_scrub_event_remove_prompt_em_extra_exception_e_breadcrumb() -> None:
    event = {
        "message": "falha com prompt sensivel e user@example.com",
        "user": {"email": "user@example.com", "id": "u1"},
        "request": {
            "headers": {"Authorization": "Bearer token", "X-Test": "ok"},
            "data": {"prompt": "segredo"},
            "cookies": {"session": "abc"},
            "query_string": "prompt=segredo",
            "url": "https://cdn/x?X-Amz-Signature=deadbeef",
        },
        "exception": {
            "values": [
                {
                    "value": "prompt=segredo ip=10.1.2.3",
                    "stacktrace": {
                        "frames": [{"vars": {"prompt": "segredo", "safe": "ok"}}]
                    },
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {
                    "message": "prompt=segredo user@example.com",
                    "data": {"prompt": "segredo", "url": "https://x?X-Amz-Signature=abc"},
                }
            ]
        },
        "extra": {"prompt": "segredo", "object_key": "generations/1/original.png"},
        "contexts": {"custom": {"email": "user@example.com"}},
        "tags": {"prompt": "segredo"},
    }
    scrubbed = _scrub_event(event, None)
    assert scrubbed is not None
    serialized = repr(scrubbed)
    assert "segredo" not in serialized
    assert "user@example.com" not in serialized
    assert "10.1.2.3" not in serialized
    assert "deadbeef" not in serialized
    assert "generations/1/original.png" not in serialized
    assert "user" not in scrubbed
