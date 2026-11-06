"""Testes da validacao de upload PNG/JPEG (Fase 2, Bloco 5)."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from modules.image_generation.domain.image_upload import (
    ImageUploadTooLargeError,
    InvalidImageUploadError,
    inspect_uploaded_image,
    normalize_uploaded_image,
)


def _png(width: int = 64, height: int = 48) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def _jpeg(width: int = 64, height: int = 48) -> bytes:
    payload = (
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03"
        + b"\x00" * 9
    )
    return b"\xff\xd8\xff\xc0" + (len(payload) + 2).to_bytes(2, "big") + payload


@pytest.mark.unit
def test_png_valido_devolve_dimensoes_reais() -> None:
    info = inspect_uploaded_image(
        _png(320, 200),
        declared_content_type="image/png",
        max_bytes=1024 * 1024,
        max_dimension=8192,
    )
    assert info.content_type == "image/png"
    assert (info.width, info.height) == (320, 200)
    assert info.size_bytes == len(_png(320, 200))


@pytest.mark.unit
def test_jpeg_valido_devolve_dimensoes_reais() -> None:
    info = inspect_uploaded_image(
        _jpeg(640, 480),
        declared_content_type="image/jpeg",
        max_bytes=1024 * 1024,
        max_dimension=8192,
    )
    assert info.content_type == "image/jpeg"
    assert (info.width, info.height) == (640, 480)


@pytest.mark.unit
def test_tipo_declarado_divergente_e_recusado() -> None:
    with pytest.raises(InvalidImageUploadError) as exc:
        inspect_uploaded_image(
            _png(),
            declared_content_type="image/jpeg",
            max_bytes=1024,
            max_dimension=8192,
        )
    assert exc.value.code == "invalid_image_upload"


@pytest.mark.unit
def test_formato_nao_suportado_e_recusado() -> None:
    with pytest.raises(InvalidImageUploadError):
        inspect_uploaded_image(
            b"GIF89a....",
            declared_content_type="image/gif",
            max_bytes=1024,
            max_dimension=8192,
        )


@pytest.mark.unit
def test_arquivo_acima_do_limite_e_recusado() -> None:
    with pytest.raises(ImageUploadTooLargeError) as exc:
        inspect_uploaded_image(
            _png(),
            declared_content_type="image/png",
            max_bytes=10,
            max_dimension=8192,
        )
    assert exc.value.code == "image_too_large"
    assert exc.value.http_status == 413


@pytest.mark.unit
def test_dimensoes_acima_do_limite_sao_recusadas() -> None:
    with pytest.raises(InvalidImageUploadError):
        inspect_uploaded_image(
            _png(9000, 100),
            declared_content_type="image/png",
            max_bytes=1024 * 1024,
            max_dimension=8192,
        )


@pytest.mark.unit
def test_cabecalho_corrompido_e_recusado() -> None:
    with pytest.raises(InvalidImageUploadError):
        inspect_uploaded_image(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
            declared_content_type="image/png",
            max_bytes=1024,
            max_dimension=8192,
        )


@pytest.mark.unit
def test_arquivo_vazio_e_recusado() -> None:
    with pytest.raises(InvalidImageUploadError):
        inspect_uploaded_image(
            b"",
            declared_content_type="image/png",
            max_bytes=1024,
            max_dimension=8192,
        )


@pytest.mark.unit
def test_normalizacao_remove_metadados_e_reencoda_png() -> None:
    image = Image.new("RGB", (64, 48), (10, 20, 30))
    info = PngInfo()
    info.add_text("prompt", "segredo")
    info.add_text("comment", "dados")
    raw = BytesIO()
    image.save(raw, format="PNG", pnginfo=info)
    normalized = normalize_uploaded_image(raw.getvalue())
    result = Image.open(BytesIO(normalized))
    assert result.format == "PNG"
    assert "prompt" not in result.text
    assert "comment" not in result.text
    assert result.size == (64, 48)


@pytest.mark.unit
def test_normalizacao_rejeita_pixels_acima_do_limite() -> None:
    raw = BytesIO()
    Image.new("RGB", (640, 480), (1, 2, 3)).save(raw, format="PNG")
    with pytest.raises(InvalidImageUploadError):
        normalize_uploaded_image(raw.getvalue(), max_pixels=1000)


@pytest.mark.unit
def test_normalizacao_rejeita_arquivo_que_pillow_nao_decodifica() -> None:
    with pytest.raises(InvalidImageUploadError):
        normalize_uploaded_image(_png()[:30] + b"lixo")
