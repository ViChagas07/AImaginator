"""Guarda de infra local em desenvolvimento e precedencia de .env."""

from __future__ import annotations

from pathlib import Path

import pytest

from infra.dev_guard import enforce_local_infra, find_remote_infra
from infra.settings import Settings, resolve_env_files


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "secret_key": "k" * 64,
        "database_url": "postgresql+asyncpg://u:p@localhost:5433/db",
        "auto_migrate": False,
        "app_env": "development",
        "allow_remote_infra_in_dev": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.unit
def test_infra_local_e_aceita() -> None:
    settings = _settings(
        redis_url="redis://localhost:6380/0",
        celery_broker_url="amqp://guest:guest@rabbitmq:5672//",
        celery_result_backend="redis://redis:6379/1",
        s3_endpoint_url="http://minio:9000",
    )
    assert find_remote_infra(settings) == []
    enforce_local_infra(settings)


@pytest.mark.unit
def test_infra_remota_falha_sem_vazar_credenciais() -> None:
    settings = _settings(
        redis_url="rediss://user:supersecret@remote-redis.example:6379/0",
    )
    remote = find_remote_infra(settings)
    assert [(r.component, r.host) for r in remote] == [("redis", "remote-redis.example")]
    with pytest.raises(RuntimeError) as exc:
        enforce_local_infra(settings)
    message = str(exc.value)
    assert "redis=remote-redis.example" in message
    assert "supersecret" not in message
    assert "ALLOW_REMOTE_INFRA_IN_DEV" in message


@pytest.mark.unit
def test_allow_remote_infra_em_dev_permite() -> None:
    settings = _settings(
        allow_remote_infra_in_dev=True,
        redis_url="rediss://remote.example:6379/0",
    )
    enforce_local_infra(settings)


@pytest.mark.unit
def test_producao_nao_e_afetada() -> None:
    settings = _settings(
        app_env="production",
        redis_url="rediss://remote.example:6379/0",
    )
    enforce_local_infra(settings)


@pytest.mark.unit
def test_s3_vazio_e_ignorado() -> None:
    settings = _settings(s3_endpoint_url="")
    assert find_remote_infra(settings) == []


@pytest.mark.unit
def test_env_development_tem_precedencia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV_FILE", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    (tmp_path / ".env").write_text("APP_ENV=production\nDATABASE_URL=prod\n", encoding="utf-8")
    (tmp_path / ".env.development").write_text(
        "APP_ENV=development\nDATABASE_URL=dev\n", encoding="utf-8"
    )

    assert resolve_env_files() == (".env.development",)


@pytest.mark.unit
def test_env_de_producao_nao_e_carregado_em_dev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV_FILE", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    (tmp_path / ".env").write_text(
        "APP_ENV=production\nSECRET_KEY=prod\nDATABASE_URL=prod-db\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.development").write_text(
        "APP_ENV=development\nSECRET_KEY=" + "d" * 64 + "\nDATABASE_URL=dev-db\n",
        encoding="utf-8",
    )

    env_files = resolve_env_files()
    assert env_files == (".env.development",)
    settings = Settings(
        _env_file=env_files[0],
        feature_image_generation_enabled=False,
        database_url="postgresql+asyncpg://u:p@localhost:5433/db",
        auto_migrate=False,
    )
    assert settings.secret_key == "d" * 64


@pytest.mark.unit
def test_app_env_lido_do_env_escolhe_development(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV_FILE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    (tmp_path / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
    (tmp_path / ".env.development").write_text("APP_ENV=development\n", encoding="utf-8")
    assert resolve_env_files() == (".env.development",)


@pytest.mark.unit
def test_app_env_production_nao_carrega_development(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV_FILE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    (tmp_path / ".env").write_text("APP_ENV=production\n", encoding="utf-8")
    (tmp_path / ".env.development").write_text("APP_ENV=development\n", encoding="utf-8")
    assert resolve_env_files() == (".env",)


@pytest.mark.unit
def test_env_file_explicito_vence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV_FILE", ".env.custom")
    (tmp_path / ".env.development").write_text("APP_ENV=development\n", encoding="utf-8")
    assert resolve_env_files() == (".env.custom",)
