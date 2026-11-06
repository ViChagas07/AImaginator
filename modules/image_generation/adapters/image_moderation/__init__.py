"""Adapters de moderacao de imagem."""

from modules.image_generation.adapters.image_moderation.fake import FakeImageModerator
from modules.image_generation.adapters.image_moderation.local import LocalImageModerator

__all__ = ["FakeImageModerator", "LocalImageModerator"]
