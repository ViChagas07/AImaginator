"""Testes do adapter sd-cli: comando, progresso, timeout, erros e recursos."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.adapters.sdcpp.command import (
    build_sdcpp_command,
    ensure_allowed_dimensions,
    sanitize_prompt_argument,
)
from modules.image_generation.adapters.sdcpp.engine import (
    SdCppImageEditor,
    SdCppImageGenerator,
)
from modules.image_generation.adapters.sdcpp.progress import (
    parse_progress_line,
    progress_for_step,
)
from modules.image_generation.domain.engine_errors import (
    EngineFailedError,
    EngineOutOfMemoryError,
    EngineTimeoutError,
    InsufficientResourcesError,
    InvalidImageDimensionsError,
)
from modules.image_generation.domain.image_bytes import inspect_image_bytes


def _settings(fake_binary: Path | str, **overrides):
    values = {
        "sdcpp_binary_path": str(fake_binary),
        "sdcpp_vae_path": "C:/models dir/ae.safetensors",
        "sdcpp_clip_l_path": "C:/models dir/clip_l.safetensors",
        "sdcpp_t5xxl_path": "C:/models dir/t5xxl.gguf",
        "sdcpp_gen_model_path": "C:/models dir/flux q4.gguf",
        "sdcpp_edit_model_path": "C:/models dir/kontext q4.gguf",
        "gen_width": 512,
        "gen_height": 512,
        "gen_steps": 8,
        "gen_guidance": 3.5,
        "edit_width": 512,
        "edit_height": 512,
        "edit_steps": 8,
        "edit_guidance": 3.5,
        "generation_timeout_seconds": 10,
        "edit_timeout_seconds": 10,
        "min_free_ram_mb": 1,
        "cooldown_seconds_between_jobs": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.unit
class TestCommand:
    def test_caminhos_com_espacos_continuam_um_argumento(self) -> None:
        command = build_sdcpp_command(
            binary_path="C:/Program Files/sd-cli/sd.exe",
            vae_path="C:/Meus Modelos/ae.safetensors",
            clip_l_path="C:/Meus Modelos/clip l.safetensors",
            t5xxl_path="C:/Meus Modelos/t5 xxl.gguf",
            diffusion_model_path="C:/Meus Modelos/flux dev q4.gguf",
            prompt="a cozy cabin",
            width=512,
            height=512,
            steps=8,
            guidance=3.5,
            seed=42,
            output_path="C:/Temp Saida/result.png",
        )

        assert command[0] == "C:/Program Files/sd-cli/sd.exe"
        assert "C:/Meus Modelos/flux dev q4.gguf" in command
        assert command[command.index("-p") + 1] == "a cozy cabin"
        assert command[command.index("-o") + 1] == "C:/Temp Saida/result.png"
        assert command[command.index("--steps") + 1] == "8"
        assert command[command.index("--seed") + 1] == "42"
        assert command[command.index("--flash-attn") + 1] == "off,diffusion=on"

    def test_edicao_inclui_imagem_de_origem(self) -> None:
        command = build_sdcpp_command(
            binary_path="sd.exe",
            vae_path="ae",
            clip_l_path="clip",
            t5xxl_path="t5",
            diffusion_model_path="kontext",
            prompt="edit",
            width=448,
            height=576,
            steps=8,
            guidance=2.5,
            seed=1,
            output_path="out.png",
            source_image_path="source.png",
        )
        assert command[command.index("-r") + 1] == "source.png"
        assert command[command.index("--guidance") + 1] == "2.5"

    def test_prompt_hostil_nao_vira_opcao_nem_controle(self) -> None:
        clean = sanitize_prompt_argument('--help\n-o C:\\x\x00 "quoted" ç')
        assert clean.startswith(" --help")
        assert "\n" not in clean and "\x00" not in clean
        assert len(sanitize_prompt_argument("a" * 5000)) == 2000

    def test_prompt_unicode_e_aspas_preservados_como_texto(self) -> None:
        clean = sanitize_prompt_argument("um gato 'aspas' --help ç")
        assert clean == "um gato 'aspas' --help ç"

    def test_dimensao_arbitraria_e_rejeitada(self) -> None:
        with pytest.raises(InvalidImageDimensionsError):
            ensure_allowed_dimensions(640, 480)

    def test_todas_as_proporcoes_permitidas(self) -> None:
        for width, height in ((512, 512), (576, 448), (448, 576), (704, 384), (384, 704)):
            ensure_allowed_dimensions(width, height)


@pytest.mark.unit
class TestParserProgresso:
    def test_primeira_linha_mais_lenta(self) -> None:
        parsed = parse_progress_line("  | 1/8 - 25.2s/it")
        assert parsed is not None
        assert parsed.current == 1
        assert parsed.total == 8
        assert parsed.seconds_per_step == 25.2

    def test_linha_do_meio(self) -> None:
        parsed = parse_progress_line("| 3/8 - 19.5s/it")
        assert parsed is not None
        assert progress_for_step(parsed) == 40

    def test_barra_final_mapeia_para_90(self) -> None:
        parsed = parse_progress_line("| 8/8 - 19.4s/it|")
        assert parsed is not None
        assert progress_for_step(parsed) == 90

    def test_linha_sem_segundos(self) -> None:
        parsed = parse_progress_line("| 4/8")
        assert parsed is not None
        assert parsed.seconds_per_step is None

    def test_linhas_invalidas_sao_ignoradas(self) -> None:
        assert parse_progress_line("loading model...") is None
        assert parse_progress_line("| 9/8 - 1.0s/it") is None
        assert parse_progress_line("| 0/0 - 1.0s/it") is None


@pytest.mark.unit
class TestEngine:
    async def test_geracao_sucesso_progresso_bytes_e_seed(self, fake_sd_cli) -> None:
        settings = _settings(fake_sd_cli)
        progress: list[int] = []

        async def collect(percent: int) -> None:
            progress.append(percent)

        generator = SdCppImageGenerator(settings, available_ram_mb_fn=lambda: 16000)

        result = await generator.generate(
            prompt="a cozy cabin",
            width=512,
            height=512,
            seed=1234,
            on_progress=collect,
        )

        assert result.seed == 1234
        assert result.width == 512
        assert result.height == 512
        assert result.duration_seconds >= 0
        assert inspect_image_bytes(result.image_bytes).width == 512
        assert progress[0] == 10
        assert progress[-1] == 90
        assert progress == sorted(progress)

    async def test_seed_aleatoria_quando_ausente(self, fake_sd_cli) -> None:
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        result = await generator.generate(
            prompt="cabin", width=512, height=512, seed=None, on_progress=_noop
        )
        assert isinstance(result.seed, int)
        assert 0 <= result.seed < 2**32

    async def test_edicao_envia_origem_e_devolve_metadados(self, fake_sd_cli) -> None:
        editor = SdCppImageEditor(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        result = await editor.edit(
            prompt="make it orange",
            source_image=make_png_bytes(64, 64),
            width=448,
            height=576,
            seed=7,
            on_progress=_noop,
        )
        assert result.width == 448
        assert result.height == 576
        assert result.seed == 7

    async def test_executavel_falso_recebe_prompt_hostil_como_um_arg(
        self, fake_sd_cli, tmp_path, monkeypatch
    ) -> None:
        import json

        log = tmp_path / "args.json"
        monkeypatch.setenv("FAKE_SDCLI_ARGS_PATH", str(log))
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        await generator.generate(
            prompt='--help\n-o C:\\x "aspas"',
            width=512,
            height=512,
            seed=1,
            on_progress=_noop,
        )
        args = json.loads(log.read_text(encoding="utf-8"))
        value = args[args.index("-p") + 1]
        assert value.startswith(" --help")
        assert "\n" not in value

    async def test_oem_vira_erro_de_memoria(self, fake_sd_cli) -> None:
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        with pytest.raises(EngineOutOfMemoryError):
            await generator.generate(
                prompt="oom", width=512, height=512, seed=1, on_progress=_noop
            )

    async def test_saida_nao_zero_vira_engine_failed(self, fake_sd_cli) -> None:
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        with pytest.raises(EngineFailedError):
            await generator.generate(
                prompt="fail", width=512, height=512, seed=1, on_progress=_noop
            )

    async def test_arquivo_ausente_vira_engine_failed(self, fake_sd_cli) -> None:
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli), available_ram_mb_fn=lambda: 16000
        )
        with pytest.raises(EngineFailedError):
            await generator.generate(
                prompt="no-output", width=512, height=512, seed=1, on_progress=_noop
            )

    async def test_timeout_mata_arvore_e_limpa_temporarios(
        self, fake_sd_cli, tmp_path, monkeypatch
    ) -> None:
        import tempfile

        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        generator = SdCppImageGenerator(
            _settings(fake_sd_cli, generation_timeout_seconds=1),
            available_ram_mb_fn=lambda: 16000,
        )
        started = time.monotonic()
        with pytest.raises(EngineTimeoutError):
            await generator.generate(
                prompt="timeout", width=512, height=512, seed=1, on_progress=_noop
            )
        elapsed = time.monotonic() - started
        assert elapsed < 10
        assert not list(tmp_path.glob("aimaginator-sdcpp-*"))

    async def test_guarda_de_ram_nao_inicia_processo(self, tmp_path) -> None:
        generator = SdCppImageGenerator(
            _settings(tmp_path / "nao-existe.exe", min_free_ram_mb=6000),
            available_ram_mb_fn=lambda: 100,
        )
        with pytest.raises(InsufficientResourcesError):
            await generator.generate(
                prompt="cabin", width=512, height=512, seed=1, on_progress=_noop
            )

    async def test_cooldown_apos_job(self, fake_sd_cli) -> None:
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        generator = SdCppImageGenerator(
            _settings(fake_sd_cli, cooldown_seconds_between_jobs=2.5),
            available_ram_mb_fn=lambda: 16000,
            sleep_fn=fake_sleep,
        )
        await generator.generate(
            prompt="cabin", width=512, height=512, seed=1, on_progress=_noop
        )
        assert sleeps == [2.5]

    async def test_dimensao_invalida_nao_inicia_processo(self, tmp_path) -> None:
        generator = SdCppImageGenerator(
            _settings(tmp_path / "nao-existe.exe"), available_ram_mb_fn=lambda: 16000
        )
        with pytest.raises(InvalidImageDimensionsError):
            await generator.generate(
                prompt="cabin", width=640, height=480, seed=1, on_progress=_noop
            )


async def _noop(_: int) -> None:
    return None
