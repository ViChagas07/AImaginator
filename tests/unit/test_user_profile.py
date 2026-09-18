"""Testes das regras de negocio do perfil do usuario (modulo users)."""

from __future__ import annotations

from uuid import UUID

import pytest

from modules.users.domain.entities import User, UserSettings


@pytest.mark.unit
class TestProviderDisconnectRule:
    """Um usuario so pode desconectar o Google se tiver login alternativo."""

    def test_google_sem_senha_nao_pode_desconectar(self) -> None:
        user = User(
            email="a@x.com",
            name="Ada",
            google_sub="google-123",
            password_hash=None,
        )
        assert not user.has_alternative_login()

    def test_google_com_senha_pode_desconectar(self) -> None:
        user = User(
            email="a@x.com",
            name="Ada",
            google_sub="google-123",
            password_hash="hashed",
        )
        assert user.has_alternative_login()

    def test_usuario_local_sem_google(self) -> None:
        user = User(
            email="a@x.com",
            name="Ada",
            google_sub=None,
            password_hash="hashed",
        )
        assert user.has_alternative_login()


@pytest.mark.unit
class TestUserSettingsDefaults:
    """Valores padrao das preferencias devem ser seguros e consistentes."""

    def test_defaults(self) -> None:
        settings = UserSettings(user_id=UUID(int=0))
        assert settings.theme == "system"
        assert settings.font_size == "medium"
        assert settings.element_spacing == "comfortable"
        assert settings.locale == "pt-BR"
        assert settings.timezone == "America/Sao_Paulo"
        assert settings.email_notifications is True
        assert settings.reduced_motion is False
        assert settings.developer_mode is False
