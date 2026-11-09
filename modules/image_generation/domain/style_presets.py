"""Presets deterministicos de estilo (nunca aplicados pelo LLM)."""

from __future__ import annotations

from modules.image_generation.domain.entities import StylePreset

STYLE_FRAGMENTS: dict[StylePreset, str] = {
    StylePreset.NONE: "",
    StylePreset.PHOTOREALISTIC: (
        "photorealistic photography, natural lighting, realistic textures"
    ),
    StylePreset.ANIME: "anime illustration, clean line art, vibrant colors",
    StylePreset.OIL_PAINTING: "oil painting, visible brush strokes, canvas texture",
    StylePreset.CYBERPUNK: "cyberpunk aesthetic, neon lighting, futuristic city",
    StylePreset.WATERCOLOR: "watercolor painting, soft washes, paper texture",
    StylePreset.ISOMETRIC_3D: "isometric 3D render, clean geometry, soft shadows",
}


def apply_style_preset(prompt: str, preset: StylePreset) -> str:
    """Anexa o fragmento fechado do preset; desconhecido e rejeitado."""
    if preset not in STYLE_FRAGMENTS:
        raise ValueError("Preset de estilo desconhecido.")
    fragment = STYLE_FRAGMENTS[preset]
    if not fragment:
        return prompt.strip()
    return f"{prompt.rstrip().rstrip(',')}, {fragment}"
