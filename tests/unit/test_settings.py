"""Testes de validacao centralizada de settings (Fase 2, Bloco 2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from infra.settings import Settings


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "secret_key": "k" * 64,
        "database_url": "postgresql+asyncpg://user:pass@localhost:5433/aimaginator",
        "auto_migrate": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_defaults_dos_parametros_medidos() -> None:
    settings = _settings()

    assert settings.image_engine == "stub"
    assert settings.gen_width == 512
    assert settings.gen_height == 512
    assert settings.gen_steps == 8
    assert settings.gen_guidance == 3.5
    assert settings.edit_width == 512
    assert settings.edit_height == 512
    assert settings.edit_steps == 8
    assert settings.edit_guidance == 3.5
    assert settings.generation_timeout_seconds == 300
    assert settings.edit_timeout_seconds == 600
    assert settings.edit_upload_max_bytes == 10 * 1024 * 1024
    assert settings.edit_upload_max_dimension == 8192
    assert settings.min_free_ram_mb == 6000
    assert settings.cooldown_seconds_between_jobs == 0
    assert settings.s3_endpoint_url == ""
    assert settings.s3_public_endpoint_url == ""
    assert settings.s3_bucket == ""
    assert settings.s3_region == "us-east-1"
    assert settings.s3_presign_expires_seconds == 900
    assert settings.s3_source_retention_hours == 24
    assert settings.prompt_max_chars == 1000
    assert settings.llm_base_url == "http://localhost:1235/v1"
    assert settings.llm_model == "qwen/qwen3.5-9b"
    assert settings.llm_timeout_seconds == 90
    assert settings.llm_max_output_tokens == 400
    assert settings.llm_ttl_seconds == 60
    assert settings.llm_block_confidence == 0.5
    assert settings.moderation_store_prompt_text is False
    assert settings.mod_warn_at == 3
    assert settings.mod_block_at == 5
    assert settings.mod_block_minutes == 60
    assert settings.mod_review_at == 10
    assert settings.mod_review_block_hours == 24
    assert settings.moderation_window_hours == 24
    assert settings.image_moderation_enabled is True
    assert settings.image_moderator == "fake"
    assert settings.image_nsfw_threshold == 0.5
    assert settings.watermark_logo_path.endswith("AImaginator_pic_transparent.png")
    assert settings.watermark_width_ratio == 0.20
    assert settings.watermark_min_width_px == 96
    assert settings.watermark_margin_ratio == 0.025
    assert settings.watermark_opacity == 0.9
    assert settings.watermark_shadow is True
    assert settings.c2pa_enabled is False
    assert settings.upscale_engine == "lanczos"
    assert settings.upscale_daily_limit == 5
    assert settings.upscale_timeout_seconds == 300


def test_moderador_local_exige_pesos() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(image_moderator="local")
    message = str(exc.value)
    assert "IMAGE_NSFW_MODEL_PATH" in message
    assert "IMAGE_CLIP_MODEL_PATH" in message


def test_esrgan_exige_modelo_de_upscale() -> None:
    with pytest.raises(ValidationError):
        _settings(upscale_engine="esrgan")


def test_producao_desliga_geracao_por_padrao_e_nao_exige_sdcpp(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FEATURE_IMAGE_GENERATION_ENABLED", raising=False)
    settings = _settings(app_env="production", image_engine="sdcpp")
    assert settings.image_generation_enabled is False


def test_producao_ligada_exige_paths_do_sdcpp(monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_IMAGE_GENERATION_ENABLED", "true")
    with pytest.raises(ValidationError):
        _settings(app_env="production", image_engine="sdcpp")


def test_development_liga_geracao_por_padrao(monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_IMAGE_GENERATION_ENABLED", raising=False)
    settings = _settings(app_env="development")
    assert settings.image_generation_enabled is True


def test_watermark_precisa_existir_e_ter_alfa() -> None:
    with pytest.raises(ValidationError):
        _settings(watermark_logo_path="nao-existe.png")


def test_llm_api_key_nao_pode_ser_vazia() -> None:
    with pytest.raises(ValidationError):
        _settings(llm_api_key="")


def test_thresholds_de_moderacao_precisam_ser_crescentes() -> None:
    with pytest.raises(ValidationError):
        _settings(mod_warn_at=5, mod_block_at=3, mod_review_at=10)


def test_paths_sdcpp_vazios_por_padrao() -> None:
    settings = _settings()

    assert settings.sdcpp_binary_path == ""
    assert settings.sdcpp_vae_path == ""
    assert settings.sdcpp_clip_l_path == ""
    assert settings.sdcpp_t5xxl_path == ""
    assert settings.sdcpp_gen_model_path == ""
    assert settings.sdcpp_edit_model_path == ""


def test_env_sobrescreve_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEN_WIDTH", "768")
    monkeypatch.setenv("GEN_STEPS", "12")
    monkeypatch.setenv("EDIT_TIMEOUT_SECONDS", "720")
    monkeypatch.setenv("IMAGE_ENGINE", "stub")

    settings = _settings()

    assert settings.gen_width == 768
    assert settings.gen_steps == 12
    assert settings.edit_timeout_seconds == 720


def test_urls_publicas_sao_normalizadas() -> None:
    settings = _settings(
        api_base_url="https://api.example.com/",
        frontend_base_url="https://app.example.com/",
        frontend_origins="",
    )

    assert settings.api_base_url == "https://api.example.com"
    assert settings.frontend_base_url == "https://app.example.com"
    assert settings.allowed_frontend_origins == ["https://app.example.com"]


def test_frontend_origins_inclui_base_e_normaliza_extras() -> None:
    settings = _settings(
        frontend_base_url="https://app.example.com/",
        frontend_origins=" https://preview.example.com/ , https://preview.example.com ",
    )

    assert settings.allowed_frontend_origins == [
        "https://app.example.com",
        "https://preview.example.com",
    ]


def test_image_engine_invalido_falha_no_startup() -> None:
    with pytest.raises(ValidationError):
        _settings(image_engine="outro")


def test_dimensao_invalida_falha_no_startup() -> None:
    with pytest.raises(ValidationError):
        _settings(gen_width=0)


def test_steps_invalido_falha_no_startup() -> None:
    with pytest.raises(ValidationError):
        _settings(edit_steps=0)


def test_guidance_invalida_falha_no_startup() -> None:
    with pytest.raises(ValidationError):
        _settings(gen_guidance=-1)


def test_sdcpp_exige_todos_os_caminhos() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(image_engine="sdcpp")

    message = str(exc.value)
    assert "SDCPP_BINARY_PATH" in message
    assert "SDCPP_EDIT_MODEL_PATH" in message


def _sdcpp_paths() -> dict:
    return {
        "sdcpp_binary_path": "C:/ai/sd.exe",
        "sdcpp_vae_path": "C:/ai/ae.safetensors",
        "sdcpp_clip_l_path": "C:/ai/clip_l.safetensors",
        "sdcpp_t5xxl_path": "C:/ai/t5xxl.gguf",
        "sdcpp_gen_model_path": "C:/ai/flux-q4.gguf",
        "sdcpp_edit_model_path": "C:/ai/kontext-q4.gguf",
    }


def _s3_config() -> dict:
    return {
        "s3_endpoint_url": "http://localhost:9002",
        "s3_bucket": "aimaginator-dev",
        "s3_access_key": "aimaginator",
        "s3_secret_key": "aimaginator_dev_minio",
    }


def test_sdcpp_com_caminhos_e_s3_completos_e_aceito() -> None:
    settings = _settings(image_engine="sdcpp", **_sdcpp_paths(), **_s3_config())

    assert settings.image_engine == "sdcpp"
    assert settings.sdcpp_gen_model_path.endswith("flux-q4.gguf")
    assert settings.s3_bucket == "aimaginator-dev"


def test_sdcpp_aceita_aws_keys_com_endpoint_opcional() -> None:
    settings = _settings(
        image_engine="sdcpp",
        **_sdcpp_paths(),
        s3_bucket="meu-bucket",
        aws_access_key_id="aws-id",
        aws_secret_access_key="aws-secret",
    )
    assert settings.image_generation_enabled is True
    assert settings.s3_endpoint_url == ""


def test_sdcpp_sem_s3_falha_no_startup() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(image_engine="sdcpp", **_sdcpp_paths())

    assert "S3_BUCKET" in str(exc.value)


def test_s3_credenciais_sao_obrigatorias_quando_bucket_definido() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(image_engine="sdcpp", s3_bucket="bucket", **_sdcpp_paths())

    message = str(exc.value)
    assert "S3_ACCESS_KEY" in message
    assert "S3_SECRET_KEY" in message
