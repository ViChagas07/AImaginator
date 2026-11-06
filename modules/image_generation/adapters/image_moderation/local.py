"""Adapter local de moderacao de imagem (transformers/CLIP), lazy e opcional.

Este modulo so importa torch/transformers quando IMAGE_MODERATOR=local e o
moderador e efetivamente chamado. Sem o grupo opcional instalado, levanta
ImageModerationUnavailableError (fail-closed) em vez de quebrar a app.
"""

from __future__ import annotations

import asyncio
import gc
import importlib
import logging
from pathlib import Path

import psutil

from modules.image_generation.application.ports.image_moderation import (
    ImageModerationResult,
    ImageModerationScores,
    ImageModerationThresholds,
    decide_image_moderation,
)
from shared_kernel.security_errors import ImageModerationUnavailableError

logger = logging.getLogger(__name__)

_GORE_LABELS = [
    "a photo of graphic gore, blood and mutilated bodies",
    "a normal, safe photo",
]
_HATE_LABELS = [
    "a photo with hate symbols or hateful extremist imagery",
    "a normal, safe photo",
]
_SELF_HARM_LABELS = [
    "a photo of self-harm, suicide or a person hurting themselves",
    "a normal, safe photo",
]


class LocalImageModerator:
    def __init__(
        self,
        *,
        nsfw_model_path: str,
        clip_model_path: str,
        thresholds: ImageModerationThresholds | None = None,
    ) -> None:
        self._nsfw_path = nsfw_model_path
        self._clip_path = clip_model_path
        self._thresholds = thresholds or ImageModerationThresholds()
        self._nsfw_model = None
        self._nsfw_processor = None
        self._clip_model = None
        self._clip_processor = None

    async def moderate(self, image_bytes: bytes) -> ImageModerationResult:
        try:
            return await asyncio.to_thread(self._moderate_sync, image_bytes)
        except ImageModerationUnavailableError:
            raise
        except Exception as exc:
            logger.exception("image_moderation_failed")
            raise ImageModerationUnavailableError() from exc
        finally:
            self._release()

    def _moderate_sync(self, image_bytes: bytes) -> ImageModerationResult:
        try:
            from io import BytesIO

            from PIL import Image
        except ImportError as exc:
            raise ImageModerationUnavailableError() from exc
        if not self._nsfw_path or not self._clip_path:
            raise ImageModerationUnavailableError()
        if not Path(self._clip_path).exists() or not Path(self._nsfw_path).exists():
            raise ImageModerationUnavailableError()

        memory = psutil.virtual_memory()
        logger.info(
            "image_moderation_ram_before",
            extra={
                "available_mb": int(memory.available // (1024 * 1024)),
                "used_percent": memory.percent,
            },
        )
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        nsfw_score = self._nsfw_score(image)
        clip_scores = self._clip_scores(image)
        scores = ImageModerationScores(
            sexual=nsfw_score,
            gore=clip_scores.get("gore", 0.0),
            hate=clip_scores.get("hate", 0.0),
            self_harm=clip_scores.get("self_harm", 0.0),
        )
        return decide_image_moderation(scores, self._thresholds)

    def _load_nsfw(self):
        if self._nsfw_model is None:
            transformers = importlib.import_module("transformers")
            self._nsfw_processor = transformers.AutoImageProcessor.from_pretrained(
                self._nsfw_path
            )
            self._nsfw_model = transformers.AutoModelForImageClassification.from_pretrained(
                self._nsfw_path
            )
            self._nsfw_model.eval()
        return self._nsfw_processor, self._nsfw_model

    def _nsfw_score(self, image) -> float:
        import torch

        processor, model = self._load_nsfw()
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        labels = getattr(model.config, "id2label", {}) or {}
        for index, label in labels.items():
            if "nsfw" in str(label).lower() or "explicit" in str(label).lower():
                return float(probs[int(index)])
        return float(probs.max())

    def _load_clip(self):
        if self._clip_model is None:
            transformers = importlib.import_module("transformers")
            self._clip_processor = transformers.CLIPProcessor.from_pretrained(
                self._clip_path
            )
            self._clip_model = transformers.CLIPModel.from_pretrained(self._clip_path)
            self._clip_model.eval()
        return self._clip_processor, self._clip_model

    def _clip_scores(self, image) -> dict[str, float]:
        import torch

        processor, model = self._load_clip()
        scores: dict[str, float] = {}
        for name, labels in (
            ("gore", _GORE_LABELS),
            ("hate", _HATE_LABELS),
            ("self_harm", _SELF_HARM_LABELS),
        ):
            inputs = processor(
                text=labels, images=image, return_tensors="pt", padding=True
            )
            with torch.no_grad():
                logits = model(**inputs).logits_per_image
            probs = torch.softmax(logits, dim=-1)[0]
            scores[name] = float(probs[0])
        return scores

    def _release(self) -> None:
        try:
            import torch

            self._nsfw_model = None
            self._nsfw_processor = None
            self._clip_model = None
            self._clip_processor = None
            gc.collect()
            if torch.cuda.is_available():  # pragma: no cover - CPU em producao
                torch.cuda.empty_cache()
            memory = psutil.virtual_memory()
            logger.info(
                "image_moderator_released",
                extra={
                    "ram_used_percent": memory.percent,
                    "ram_available_mb": int(memory.available // (1024 * 1024)),
                },
            )
        except Exception:
            logger.debug("image_moderator_release_failed", exc_info=True)
