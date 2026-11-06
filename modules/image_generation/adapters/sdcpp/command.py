"""Montagem pura do comando do sd-cli (argumentos sempre em lista)."""

from __future__ import annotations

import unicodedata

from modules.image_generation.domain.engine_errors import InvalidImageDimensionsError
from modules.image_generation.domain.entities import ASPECT_RATIO_DIMENSIONS

ALLOWED_DIMENSIONS: frozenset[tuple[int, int]] = frozenset(
    ASPECT_RATIO_DIMENSIONS.values()
)
MAX_PROMPT_ARG_CHARS = 2000


def sanitize_prompt_argument(prompt: str) -> str:
    """Remove controles/quebras e impede que o valor seja lido como opcao."""
    normalized = unicodedata.normalize("NFKC", prompt)
    cleaned = "".join(
        " " if ch in "\r\n\t" else ch
        for ch in normalized
        if ch in "\r\n\t" or unicodedata.category(ch)[0] != "C"
    )
    cleaned = " ".join(cleaned.split())[:MAX_PROMPT_ARG_CHARS].strip()
    if not cleaned:
        raise ValueError("Prompt vazio apos sanitizacao.")
    return f" {cleaned}" if cleaned.startswith("-") else cleaned


def ensure_allowed_dimensions(width: int, height: int) -> None:
    if (width, height) not in ALLOWED_DIMENSIONS:
        raise InvalidImageDimensionsError(
            "Proporcao nao suportada. Use 1:1, 4:3, 3:4, 16:9 ou 9:16."
        )


def build_sdcpp_command(
    *,
    binary_path: str,
    vae_path: str,
    clip_l_path: str,
    t5xxl_path: str,
    diffusion_model_path: str,
    prompt: str,
    width: int,
    height: int,
    steps: int,
    guidance: float,
    seed: int,
    output_path: str,
    source_image_path: str | None = None,
) -> list[str]:
    """Monta o argv do sd-cli. Nunca usa shell: cada valor e um argumento."""
    ensure_allowed_dimensions(width, height)
    command = [
        binary_path,
        "--diffusion-model",
        diffusion_model_path,
        "--vae",
        vae_path,
        "--clip_l",
        clip_l_path,
        "--t5xxl",
        t5xxl_path,
        "-p",
        sanitize_prompt_argument(prompt),
        "--cfg-scale",
        "1.0",
        "--guidance",
        str(guidance),
        "--sampling-method",
        "euler",
        "--flash-attn",
        "off,diffusion=on",
        "-W",
        str(width),
        "-H",
        str(height),
        "--steps",
        str(steps),
        "--seed",
        str(seed),
        "-o",
        output_path,
    ]
    if source_image_path is not None:
        command.extend(["-r", source_image_path])
    return command
