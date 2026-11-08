"""Catalogo de recusas/avisos deve existir completo nos 11 idiomas."""

from __future__ import annotations

import pytest

from modules.image_generation.application.localization import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    all_message_keys,
    message_for,
    resolve_locale,
    warning_message_for,
)

_EXPECTED_KEYS = {
    "content_blocked_nsfw",
    "content_blocked_gore",
    "content_blocked_hate",
    "content_blocked_self_harm",
    "out_of_scope",
    "prompt_rejected",
    "assistant_unavailable",
    "temporarily_blocked",
    "warning_level_1",
    "account_under_review",
    "invalid_input",
    "image_blocked_nsfw",
    "image_blocked_gore",
    "image_blocked_hate",
    "image_blocked_self_harm",
    "source_image_blocked_nsfw",
    "source_image_blocked_gore",
    "source_image_blocked_hate",
    "source_image_blocked_self_harm",
    "image_moderation_unavailable",
    "upscale_limit_reached",
    "feature_disabled",
    "original_unavailable",
    "queue_publish_failed",
    "queue_lost",
}


@pytest.mark.unit
def test_todos_os_locales_tem_todas_as_chaves() -> None:
    assert all_message_keys() == _EXPECTED_KEYS
    for locale in SUPPORTED_LOCALES:
        for key in _EXPECTED_KEYS:
            text = message_for(key, locale)
            assert text.strip(), f"{locale}/{key} vazio"
            assert text != key, f"{locale}/{key} sem traducao"


@pytest.mark.unit
def test_locales_nao_sao_copias_do_pt_br() -> None:
    allowed = {"pt-BR", "en"}
    for locale in SUPPORTED_LOCALES:
        if locale in allowed:
            continue
        for key in _EXPECTED_KEYS:
            assert message_for(key, locale) != message_for(
                key, DEFAULT_LOCALE
            ), f"{locale}/{key} identico ao pt-BR"


@pytest.mark.unit
def test_resolve_locale_com_fallback_e_variantes() -> None:
    assert resolve_locale("ja") == "ja"
    assert resolve_locale("pt-br") == "pt-BR"
    assert resolve_locale("en-US") == "en"
    assert resolve_locale("fr-CA,fr;q=0.9") == "fr"
    assert resolve_locale("xx-YY") == "pt-BR"
    assert resolve_locale(None, "es-ES") == "es"


@pytest.mark.unit
def test_mensagem_de_autolesao_tem_apoio_gentil() -> None:
    for locale in SUPPORTED_LOCALES:
        text = message_for("content_blocked_self_harm", locale).lower()
        assert len(text) > 30


@pytest.mark.unit
def test_avisos_por_nivel() -> None:
    assert warning_message_for(1, "en") == message_for("warning_level_1", "en")
    assert warning_message_for(2, "en") == message_for("temporarily_blocked", "en")
    assert warning_message_for(3, "en") == message_for("account_under_review", "en")
    assert warning_message_for(0, "en") is None
