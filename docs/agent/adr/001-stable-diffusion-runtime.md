# ADR-001 — stable-diffusion.cpp como runtime local

## Status
Aceito.

## Contexto
FLUX.1 Dev e FLUX.1 Kontext precisam rodar localmente em Windows com GPU AMD
de 8 GB (Vulkan), sem CUDA. O spike mediu tempos e VRAM.

## Decisão
Usar `sd-cli` do stable-diffusion.cpp como subprocesso, com FLUX.1 Dev Q4_K_S
para geração e Kontext Q4_0 para edição, timeouts separados e kill da árvore.

## Consequências
- Nenhum teste executa o binário/modelo real; usamos um executável falso.
- Modelos ficam em caminhos configuráveis (`SDCPP_*`) e não são versionados.
- Licença do FLUX dev é não comercial; uso comercial exige outra licença.
