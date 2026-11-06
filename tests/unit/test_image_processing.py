"""Marca d'agua e metadados de IA com imagens sinteticas (Pillow)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from modules.image_generation.adapters.image_processing import (
    AiMetadataWriter,
    C2PASigner,
    PillowWatermarker,
)
from modules.image_generation.domain.entities import ASPECT_RATIO_DIMENSIONS

LOGO = "modules/image_generation/assets/AImaginator_pic_transparent.png"


def _png(width: int, height: int, *, mode: str = "RGB", color=(20, 30, 40)) -> bytes:
    image = Image.new(mode, (width, height), color)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _open(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


@pytest.fixture
def watermarker() -> PillowWatermarker:
    return PillowWatermarker(logo_path=LOGO)


@pytest.mark.unit
def test_geometria_exata_do_canto_inferior_direito(watermarker) -> None:
    x, y, width, height, margin = watermarker.geometry(704, 384)
    assert margin == 18  # 704 * 0.025
    assert width == 141  # 704 * 0.20
    assert x == 704 - width - margin
    assert y == 384 - height - margin


@pytest.mark.unit
def test_marca_nao_altera_tamanho_nem_bytes_originais(watermarker) -> None:
    original = _png(512, 512)
    before = bytes(original)
    result = watermarker.apply(original)

    assert original == before
    assert _open(result).size == (512, 512)
    assert result != original


@pytest.mark.unit
def test_alfa_preservado_em_rgba(watermarker) -> None:
    image = Image.new("RGBA", (512, 512), (10, 20, 30, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    result = watermarker.apply(out.getvalue())

    rendered = _open(result)
    assert rendered.mode == "RGBA"
    assert rendered.getpixel((0, 0))[3] == 0
    # A logo cobre o canto inferior direito, onde o alfa deixa de ser 0.
    x, y, logo_w, logo_h, _ = watermarker.geometry(512, 512)
    assert rendered.getpixel((x + logo_w // 2, y + logo_h // 2))[3] > 0


@pytest.mark.unit
@pytest.mark.parametrize("dimensions", ASPECT_RATIO_DIMENSIONS.values())
def test_todas_as_proporcoes_permitidas(watermarker, dimensions) -> None:
    width, height = dimensions
    result = watermarker.apply(_png(width, height))
    assert _open(result).size == (width, height)


@pytest.mark.unit
def test_imagem_pequena_nao_estoura(watermarker) -> None:
    result = watermarker.apply(_png(64, 64))
    assert _open(result).size == (64, 64)


@pytest.mark.unit
def test_cache_da_logo_por_tamanho(watermarker) -> None:
    watermarker.apply(_png(512, 512))
    watermarker.apply(_png(512, 512))
    assert len(watermarker._cache) == 1


@pytest.mark.unit
def test_metadados_de_ia_sem_dados_pessoais() -> None:
    result = AiMetadataWriter().apply(
        _png(512, 512),
        model_name="FLUX.1 Dev",
        created_at=datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
    )
    image = _open(result)
    assert image.text["DigitalSourceType"] == "trainedAlgorithmicMedia"
    assert image.text["Generator"] == "AImaginator"
    assert image.text["AI Model"] == "FLUX.1 Dev"
    assert image.text["AI Generated At"] == "2026-11-06T12:00:00Z"
    xmp = image.text["XML:com.adobe.xmp"]
    assert "trainedAlgorithmicMedia" in xmp
    assert "AImaginator" in xmp
    assert "FLUX.1 Dev" in xmp

    joined = " ".join(image.text.values()).lower()
    for forbidden in ("prompt", "seed", "user", "@", "e-mail", "email"):
        assert forbidden not in joined


@pytest.mark.unit
def test_c2pa_desligado_nao_altera_fluxo() -> None:
    original = _png(32, 32)
    assert C2PASigner(enabled=False).sign(original) == original


@pytest.mark.unit
def test_upscale_aplicando_marca_e_metadados(watermarker) -> None:
    base = watermarker.apply(_png(512, 512))
    upscaled = Image.open(io.BytesIO(base)).resize((1024, 1024), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    upscaled.save(out, format="PNG")
    watermarked = watermarker.apply(out.getvalue())
    final = AiMetadataWriter().apply(watermarked, model_name="FLUX.1 Dev")
    assert _open(final).size == (1024, 1024)
    assert _open(final).text["AI Model"] == "FLUX.1 Dev"
