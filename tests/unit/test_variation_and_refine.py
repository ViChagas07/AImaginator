"""Variacoes, refinamento encadeado e seed (backend)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.image_generation.application.schemas import EditImageInput, GenerateImageInput
from modules.image_generation.application.use_cases.create_variation import CreateVariation
from modules.image_generation.application.use_cases.edit_image import EditImageFromPrompt
from modules.image_generation.application.use_cases.generate_image import (
    GenerateImageAnonymous,
    GenerateImageFromPrompt,
)
from modules.image_generation.domain.entities import (
    AspectRatio,
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.url_policy import UrlPolicy
from shared_kernel.errors import DomainError, ForbiddenError
from tests.conftest import (
    InMemoryGenerationRepository,
    InMemoryUserRepository,
    PassThroughTopicGuard,
    SpyEventPublisher,
    SpyPromptQuota,
    SpyTaskQueue,
)


def _done(source: Generation) -> Generation:
    source.transition_to(GenerationStatus.PROCESSING)
    source.transition_to(GenerationStatus.DONE)
    source.result_image_url = "https://cdn.example/result.png"
    source.result_object_key = f"generations/{source.id}/result.png"
    source.original_object_key = f"generations/{source.id}/original.png"
    return source


def _auth_generate(repo, user_repo, queue, quota):
    return GenerateImageFromPrompt(
        generations=repo,
        users=user_repo,
        task_queue=queue,
        prompt_guard=PromptInjectionGuard(),
        topic_guard=PassThroughTopicGuard(),
        events=SpyEventPublisher(),
        prompt_quota=quota,
    )


@pytest.mark.unit
class TestSeed:
    async def test_seed_do_input_e_salva_e_devolvida(self, sample_user) -> None:
        repo = InMemoryGenerationRepository()
        use_case = _auth_generate(
            repo, InMemoryUserRepository(sample_user), SpyTaskQueue(), SpyPromptQuota()
        )
        output = await use_case.execute(
            user=sample_user,
            data=GenerateImageInput(prompt="um castelo", seed=123456, aspect_ratio="4:3"),
        )
        saved = await repo.get_by_id(output.id)
        assert saved is not None
        assert saved.seed == 123456
        assert output.seed == 123456
        assert output.aspect_ratio is AspectRatio.FOUR_THREE

    def test_seed_fora_dos_limites_e_rejeitada(self) -> None:
        with pytest.raises(ValidationError):
            GenerateImageInput(prompt="um castelo", seed=-1)
        with pytest.raises(ValidationError):
            GenerateImageInput(prompt="um castelo", seed=2**32)


@pytest.mark.unit
class TestVariation:
    async def test_variacao_mantem_prompt_e_proporcao_e_sorteia_seed(
        self, sample_user
    ) -> None:
        repo = InMemoryGenerationRepository()
        source = _done(
            Generation(
                user_id=sample_user.id,
                kind=GenerationKind.GENERATE,
                prompt="um castelo nas nuvens",
                aspect_ratio=AspectRatio.LANDSCAPE,
                seed=42,
                style_preset="anime",
            )
        )
        await repo.save(source)
        user_repo = InMemoryUserRepository(sample_user)
        quota = SpyPromptQuota()
        queue = SpyTaskQueue()
        variation = CreateVariation(
            generations=repo,
            generate_authenticated=_auth_generate(repo, user_repo, queue, quota),
        )

        output = await variation.execute(
            generation_id=source.id,
            user=sample_user,
            anonymous_session_id=None,
            locale="pt-BR",
        )

        assert output.id != source.id
        assert output.prompt == source.prompt
        assert output.aspect_ratio is AspectRatio.LANDSCAPE
        assert output.seed is not None
        assert 0 <= output.seed <= 2**32 - 1
        assert output.seed != source.seed
        assert quota.calls == [f"user:{sample_user.id}"]
        assert sample_user.generation_credits == 4
        assert queue.kinds == ["generate"]

    async def test_anonimo_so_varia_a_propria_sessao(self) -> None:
        repo = InMemoryGenerationRepository()
        source = _done(
            Generation(
                user_id=None,
                anonymous_session_id="anon-1",
                kind=GenerationKind.GENERATE,
                prompt="um gato",
            )
        )
        await repo.save(source)
        quota = SpyPromptQuota()
        variation = CreateVariation(
            generations=repo,
            generate_anonymous=GenerateImageAnonymous(
                generations=repo,
                task_queue=SpyTaskQueue(),
                prompt_guard=PromptInjectionGuard(),
                topic_guard=PassThroughTopicGuard(),
                prompt_quota=quota,
            ),
        )
        output = await variation.execute(
            generation_id=source.id,
            user=None,
            anonymous_session_id="anon-1",
        )
        assert output.prompt == "um gato"
        assert quota.calls == ["anon:anon-1"]

        with pytest.raises(ForbiddenError):
            await variation.execute(
                generation_id=source.id,
                user=None,
                anonymous_session_id="anon-2",
            )

    async def test_nao_permite_variar_geracao_de_outro_usuario(self) -> None:
        repo = InMemoryGenerationRepository()
        source = _done(
            Generation(
                user_id=uuid4(),
                kind=GenerationKind.GENERATE,
                prompt="um gato",
            )
        )
        await repo.save(source)
        variation = CreateVariation(generations=repo)
        with pytest.raises(ForbiddenError):
            await variation.execute(
                generation_id=source.id, user=None, anonymous_session_id="anon-1"
            )

    async def test_nao_permite_variar_geracao_nao_concluida(self, sample_user) -> None:
        repo = InMemoryGenerationRepository()
        source = Generation(
            user_id=sample_user.id, kind=GenerationKind.GENERATE, prompt="um gato"
        )
        await repo.save(source)
        variation = CreateVariation(generations=repo)
        with pytest.raises(DomainError):
            await variation.execute(
                generation_id=source.id, user=sample_user, anonymous_session_id=None
            )


@pytest.mark.unit
class TestRefine:
    def _edit(self, repo, user_repo, quota, queue):
        return EditImageFromPrompt(
            generations=repo,
            users=user_repo,
            task_queue=queue,
            prompt_guard=PromptInjectionGuard(),
            topic_guard=PassThroughTopicGuard(),
            url_policy=UrlPolicy(frozenset({"images.unsplash.com"})),
            events=SpyEventPublisher(),
            prompt_quota=quota,
        )

    async def test_refinar_usa_chave_do_s3_e_grava_parent(self, sample_user) -> None:
        repo = InMemoryGenerationRepository()
        source = _done(
            Generation(
                user_id=sample_user.id,
                kind=GenerationKind.GENERATE,
                prompt="um castelo",
                aspect_ratio=AspectRatio.FOUR_THREE,
            )
        )
        await repo.save(source)
        quota = SpyPromptQuota()
        use_case = self._edit(
            repo, InMemoryUserRepository(sample_user), quota, SpyTaskQueue()
        )
        output = await use_case.execute(
            user=sample_user,
            data=EditImageInput(
                prompt="deixe o ceu alaranjado",
                source_generation_id=source.id,
                aspect_ratio=AspectRatio.FOUR_THREE,
            ),
        )
        saved = await repo.get_by_id(output.id)
        assert saved is not None
        assert saved.kind is GenerationKind.EDIT
        assert saved.parent_generation_id == source.id
        assert saved.source_object_key == source.original_object_key
        assert saved.source_image_url is None
        assert saved.source_object_key is not None
        assert quota.calls == [f"user:{sample_user.id}"]

    async def test_refinar_rejeita_geracao_de_outro_usuario(self, sample_user) -> None:
        repo = InMemoryGenerationRepository()
        source = _done(
            Generation(
                user_id=uuid4(),
                kind=GenerationKind.GENERATE,
                prompt="um castelo",
            )
        )
        await repo.save(source)
        use_case = self._edit(repo, InMemoryUserRepository(sample_user), None, SpyTaskQueue())
        with pytest.raises(ForbiddenError):
            await use_case.execute(
                user=sample_user,
                data=EditImageInput(
                    prompt="mude o ceu", source_generation_id=source.id
                ),
            )

    async def test_refinar_rejeita_geracao_nao_concluida(self, sample_user) -> None:
        repo = InMemoryGenerationRepository()
        source = Generation(
            user_id=sample_user.id, kind=GenerationKind.GENERATE, prompt="um castelo"
        )
        await repo.save(source)
        use_case = self._edit(repo, InMemoryUserRepository(sample_user), None, SpyTaskQueue())
        with pytest.raises(DomainError):
            await use_case.execute(
                user=sample_user,
                data=EditImageInput(
                    prompt="mude o ceu", source_generation_id=source.id
                ),
            )

    def test_edicao_exige_exatamente_uma_origem(self) -> None:
        with pytest.raises(ValidationError):
            EditImageInput(prompt="mude o ceu")
        with pytest.raises(ValidationError):
            EditImageInput(
                prompt="mude o ceu",
                source_image_url="https://images.unsplash.com/photo-1",
                source_generation_id=uuid4(),
            )
