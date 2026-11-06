"""Contrato publico do modulo image_generation.

Unica superficie importavel por outros modulos (spec secao 3.2).
"""

from __future__ import annotations

from modules.image_generation.application.schemas import (
    EditImageInput,
    GenerateImageInput,
    GenerationOutput,
    GenerationPage,
    GenerationProgressEvent,
    RenameGenerationInput,
)
from modules.image_generation.application.use_cases.create_upscale import CreateUpscale
from modules.image_generation.application.use_cases.create_variation import CreateVariation
from modules.image_generation.application.use_cases.edit_image import (
    CreateEditFromUpload,
    EditImageFromPrompt,
)
from modules.image_generation.application.use_cases.gallery_management import (
    ClaimAnonymousArts,
    DeleteGeneration,
    RenameGeneration,
)
from modules.image_generation.application.use_cases.generate_image import (
    GenerateImageAnonymous,
    GenerateImageFromPrompt,
)
from modules.image_generation.application.use_cases.list_showcase import ListPublicShowcase
from modules.image_generation.application.use_cases.process_generation import ProcessGeneration
from modules.image_generation.application.use_cases.read_generations import (
    GetGeneration,
    ListUserGenerations,
)
from modules.image_generation.domain.entities import (
    ASPECT_RATIO_DIMENSIONS,
    AspectRatio,
    Generation,
    GenerationStatus,
)

__all__ = [
    "ASPECT_RATIO_DIMENSIONS",
    "AspectRatio",
    "ClaimAnonymousArts",
    "CreateUpscale",
    "CreateVariation",
    "CreateEditFromUpload",
    "DeleteGeneration",
    "EditImageFromPrompt",
    "EditImageInput",
    "GenerateImageAnonymous",
    "GenerateImageFromPrompt",
    "GenerateImageInput",
    "Generation",
    "GenerationOutput",
    "GenerationPage",
    "GenerationProgressEvent",
    "GenerationStatus",
    "GetGeneration",
    "ListPublicShowcase",
    "ListUserGenerations",
    "ProcessGeneration",
    "RenameGeneration",
    "RenameGenerationInput",
]
