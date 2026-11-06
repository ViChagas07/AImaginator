"""Validacao de upload de imagem de edicao (PNG/JPEG), sem processar a imagem.

Nao depende de Pillow: le assinatura e cabecalho (IHDR/SOF) para obter tipo e
dimensoes reais. O conteudo e descartado apos a validacao; storage e runtime
Kontext ficam para a fase de integracao.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from modules.image_generation.domain.image_bytes import (
    JPEG_SIGNATURE,
    PNG_SIGNATURE,
    InvalidImageBytesError,
    jpeg_dimensions,
    png_dimensions,
)
from shared_kernel.errors import DomainError

# Limite global do Pillow (anti decompression bomb). O limite configuravel e
# validado antes de abrir a imagem, no cabecalho.
Image.MAX_IMAGE_PIXELS = 40_000_000

_ALLOWED_PNG_TYPES = frozenset({"image/png"})
_ALLOWED_JPEG_TYPES = frozenset({"image/jpeg", "image/jpg"})


class InvalidImageUploadError(DomainError):
    """Tipo, assinatura ou dimensao invalidos."""

    code = "invalid_image_upload"


class ImageUploadTooLargeError(DomainError):
    """Arquivo acima do limite configurado."""

    code = "image_too_large"
    http_status = 413


@dataclass(frozen=True, slots=True)
class UploadedImageInfo:
    content_type: str
    width: int
    height: int
    size_bytes: int


def inspect_uploaded_image(
    data: bytes,
    *,
    declared_content_type: str | None,
    max_bytes: int,
    max_dimension: int,
    max_pixels: int = 40_000_000,
) -> UploadedImageInfo:
    """Valida bytes reais e devolve metadados. Nunca persiste o conteudo."""
    if not data:
        raise InvalidImageUploadError("Arquivo de imagem vazio.")

    if len(data) > max_bytes:
        raise ImageUploadTooLargeError(
            f"Imagem excede o limite de {max_bytes} bytes."
        )

    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()

    try:
        if data.startswith(PNG_SIGNATURE):
            if declared not in _ALLOWED_PNG_TYPES:
                raise InvalidImageUploadError("Tipo declarado nao corresponde a PNG.")
            width, height = png_dimensions(data, strict=False)
            content_type = "image/png"
        elif data.startswith(JPEG_SIGNATURE):
            if declared not in _ALLOWED_JPEG_TYPES:
                raise InvalidImageUploadError("Tipo declarado nao corresponde a JPEG.")
            width, height = jpeg_dimensions(data)
            content_type = "image/jpeg"
        else:
            raise InvalidImageUploadError("Apenas PNG ou JPEG sao aceitos.")
    except InvalidImageBytesError as exc:
        raise InvalidImageUploadError(exc.message) from exc

    if width <= 0 or height <= 0:
        raise InvalidImageUploadError("Dimensoes da imagem invalidas.")
    if width > max_dimension or height > max_dimension:
        raise InvalidImageUploadError(
            f"Dimensoes excedem o limite de {max_dimension}px."
        )
    if width * height > max_pixels:
        raise InvalidImageUploadError(
            f"Imagem excede o limite de {max_pixels} pixels."
        )

    return UploadedImageInfo(
        content_type=content_type,
        width=width,
        height=height,
        size_bytes=len(data),
    )


def normalize_uploaded_image(
    data: bytes, *, max_pixels: int = 40_000_000
) -> bytes:
    """Reencoda para PNG limpo (sem EXIF/metadados) e valida o conteudo real."""
    if max_pixels > 0:
        Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            if image.width * image.height > max_pixels:
                raise InvalidImageUploadError("Imagem excede o limite de pixels.")
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            out = BytesIO()
            image.save(out, format="PNG", optimize=True)
            return out.getvalue()
    except InvalidImageUploadError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise InvalidImageUploadError("Arquivo de imagem invalido.") from exc
