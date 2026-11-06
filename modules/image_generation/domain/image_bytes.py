"""Inspecao e validacao de bytes de imagem sem dependencia de Pillow.

Valida assinatura, cabecalho (PNG IHDR / JPEG SOF) e dimensoes. Usado antes
de persistir o resultado do motor e no upload de origem da edicao.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from shared_kernel.errors import DomainError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
PNG_CONTENT_TYPE = "image/png"
JPEG_CONTENT_TYPE = "image/jpeg"
_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    content_type: str
    width: int
    height: int


class InvalidImageBytesError(DomainError):
    code = "invalid_image"
    http_status = 422

    def __init__(self, message: str = "Imagem invalida.") -> None:
        super().__init__(message)


def inspect_image_bytes(data: bytes, *, strict: bool = True) -> ImageMetadata:
    """Detecta PNG/JPEG e devolve tipo e dimensoes reais.

    `strict=True` (resultado do motor) valida CRC do IHDR e marcador IEND.
    Uploads usam `strict=False`: a borda valida tipo/dimensoes, nao a
    integridade completa do arquivo.
    """
    if not data:
        raise InvalidImageBytesError("Imagem vazia.")

    if data.startswith(PNG_SIGNATURE):
        width, height = png_dimensions(data, strict=strict)
        return ImageMetadata(PNG_CONTENT_TYPE, width, height)
    if data.startswith(JPEG_SIGNATURE):
        width, height = jpeg_dimensions(data)
        return ImageMetadata(JPEG_CONTENT_TYPE, width, height)
    raise InvalidImageBytesError("Apenas PNG ou JPEG sao aceitos.")


def validate_image_bytes(
    data: bytes, *, expected_width: int, expected_height: int
) -> ImageMetadata:
    """Valida tipo/dimensoes esperadas antes de persistir o resultado."""
    metadata = inspect_image_bytes(data)
    if metadata.width != expected_width or metadata.height != expected_height:
        raise InvalidImageBytesError(
            "A imagem gerada nao corresponde as dimensoes solicitadas."
        )
    return metadata


def png_dimensions(data: bytes, *, strict: bool = True) -> tuple[int, int]:
    if len(data) < 33 or data[12:16] != b"IHDR":
        raise InvalidImageBytesError("Cabecalho PNG invalido.")
    if strict:
        chunk_length = int.from_bytes(data[8:12], "big")
        if chunk_length != 13:
            raise InvalidImageBytesError("Cabecalho IHDR invalido.")
        expected_crc = int.from_bytes(data[29:33], "big")
        actual_crc = zlib.crc32(data[12:29]) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise InvalidImageBytesError("CRC do cabecalho PNG invalido.")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if strict and b"IEND" not in data[-64:]:
        raise InvalidImageBytesError("PNG sem marcador de fim (IEND).")
    return width, height


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    size = len(data)
    while index + 1 < size:
        if data[index] != 0xFF:
            index += 1
            continue

        while index + 1 < size and data[index + 1] == 0xFF:
            index += 1
        if index + 1 >= size:
            break

        marker = data[index + 1]
        index += 2

        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:
            break
        if index + 2 > size:
            break

        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > size:
            break

        if marker in _SOF_MARKERS:
            if segment_length < 7:
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height

        index += segment_length

    raise InvalidImageBytesError("Nao foi possivel ler as dimensoes do JPEG.")
