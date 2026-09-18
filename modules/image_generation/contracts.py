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
from modules.image_generation.application.use_cases.edit_image import EditImageFromPrompt
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
from modules.image_generation.domain.entities import Generation, GenerationStatus

__all__ = [
    "ClaimAnonymousArts",
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
