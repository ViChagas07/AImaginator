"""Testes da gestao da galeria pessoal (renomear/excluir/reivindicar)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.application.use_cases.gallery_management import (
    ClaimAnonymousArts,
    DeleteGeneration,
    RenameGeneration,
)
from modules.image_generation.domain.entities import Generation, GenerationKind
from shared_kernel.errors import ForbiddenError, NotFoundError
from tests.conftest import InMemoryGenerationRepository


def _arte(user_id=None, *, anonymous_session_id=None) -> Generation:
    return Generation(
        user_id=user_id,
        anonymous_session_id=anonymous_session_id,
        kind=GenerationKind.GENERATE,
        prompt="uma arte",
    )


@pytest.mark.unit
class TestRenameGeneration:
    async def test_dono_renomeia(self) -> None:
        repo = InMemoryGenerationRepository()
        dono = uuid4()
        arte = _arte(dono)
        await repo.save(arte)

        output = await RenameGeneration(repo).execute(
            user_id=dono, generation_id=arte.id, title="Meu Titulo"
        )
        assert output.title == "Meu Titulo"

    async def test_nao_dono_403(self) -> None:
        repo = InMemoryGenerationRepository()
        arte = _arte(uuid4())
        await repo.save(arte)
        with pytest.raises(ForbiddenError):
            await RenameGeneration(repo).execute(
                user_id=uuid4(), generation_id=arte.id, title="x"
            )

    async def test_inexistente_404(self) -> None:
        with pytest.raises(NotFoundError):
            await RenameGeneration(InMemoryGenerationRepository()).execute(
                user_id=uuid4(), generation_id=uuid4(), title="x"
            )


@pytest.mark.unit
class TestDeleteGeneration:
    async def test_dono_exclui_soft(self) -> None:
        repo = InMemoryGenerationRepository()
        dono = uuid4()
        arte = _arte(dono)
        await repo.save(arte)
        await DeleteGeneration(repo).execute(user_id=dono, generation_id=arte.id)
        assert await repo.get_by_id(arte.id) is None  # nao aparece mais

    async def test_nao_dono_403(self) -> None:
        repo = InMemoryGenerationRepository()
        arte = _arte(uuid4())
        await repo.save(arte)
        with pytest.raises(ForbiddenError):
            await DeleteGeneration(repo).execute(user_id=uuid4(), generation_id=arte.id)


@pytest.mark.unit
class TestClaimAnonymousArts:
    async def test_migra_artes_anonimas_para_usuario(self) -> None:
        repo = InMemoryGenerationRepository()
        anon = "anon-session-1"
        user_id = uuid4()
        for _ in range(2):
            await repo.save(_arte(None, anonymous_session_id=anon))

        claimed = await ClaimAnonymousArts(repo).execute(
            anonymous_session_id=anon, user_id=user_id
        )
        assert claimed == 2
        artes = await repo.list_by_user(user_id, cursor=None, limit=10)
        assert len(artes) == 2
        assert all(a.user_id == user_id for a in artes)

    async def test_nao_migra_artes_de_outra_sessao(self) -> None:
        repo = InMemoryGenerationRepository()
        await repo.save(_arte(None, anonymous_session_id="outra-sessao"))
        claimed = await ClaimAnonymousArts(repo).execute(
            anonymous_session_id="anon-session-1", user_id=uuid4()
        )
        assert claimed == 0
