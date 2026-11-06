# FASE 1 — Spike de runtime local (FLUX + Kontext) — AImaginator

> Status: resultados **medidos manualmente** na máquina de desenvolvimento e
> registrados aqui. A Fase 2 não reexecutou os testes de modelo.
> Data do registro: 2026-11-05.
> Runtime: `stable-diffusion.cpp` Vulkan `sd-master-37bc88b`.

## 1. Máquina

| Item | Valor |
|---|---|
| SO | Windows 11 |
| CPU | AMD Ryzen 7 5800X (8C/16T) |
| RAM | ~16 GB (15,93 GB visíveis) |
| GPU | AMD Radeon RX 6500 XT, **8 GB de VRAM dedicada** |
| VRAM medida | heap Vulkan `DEVICE_LOCAL` 7,98 GiB (8.573.157.376 bytes); budget 7,21 GiB |
| Runtime | stable-diffusion.cpp Vulkan `sd-master-37bc88b` |
| CUDA | Não (AMD/Vulkan) |

## 2. Geração — FLUX.1 Dev

Prompt fixo: `a cozy wooden cabin in a snowy forest at dusk, warm light in the windows, photorealistic`.

| Modelo | Resolução | Steps | Tempo total | Tempo de amostragem | Resultado | Cabe 100% na VRAM? |
|---|---|---:|---:|---:|---|---|
| FLUX.1 Dev Q4_K_S | 512×512 | 8 | ~202 s | 176 s | Sucesso; qualidade igual à do Q5_K_S | NÃO MEDIDO |
| FLUX.1 Dev Q4_K_S | 512×512 | 12 | ~298 s | — | Sucesso | NÃO MEDIDO |
| FLUX.1 Dev Q5_K_S | 512×512 | 12 | ~340 s | — | Sucesso | **NÃO** (7,72 GiB > budget 7,21 GiB; offload parcial) |

> **NÃO MEDIDO:** o resumo manual não registrou o pico de VRAM. A coluna
> “cabe 100% na VRAM?” deve ser preenchida na próxima execução com
> `GPU Adapter Memory > Dedicated Usage` + Gerenciador de Tarefas; não inferir
> a partir do tempo.

## 3. Edição — FLUX.1 Kontext dev

Imagem de entrada 512×512; instrução: `make the sky orange and add a small red barn`.

| Modelo | Resolução | Steps | Tempo total | Observação | Cabe 100% na VRAM? |
|---|---|---:|---:|---|---|
| FLUX Kontext dev Q4_0 | 512×512 | 8 | ~422 s | ~45,6 s/step | NÃO MEDIDO |
| FLUX Kontext dev Q4_0 | 448×448 | 8 | ~291 s | Qualidade aceitável, mas abaixo de 512 | NÃO MEDIDO |
| FLUX Kontext dev Q4_0 | 384×384 | 8 | ~216 s | Qualidade pior | NÃO MEDIDO |

**Decisão aprovada:** a edição em 512×512 **não cabe em 5 minutos**. Usar timeout
próprio de **10 minutos** para edição (`EDIT_TIMEOUT_SECONDS=600`), mantendo a
geração em 5 minutos (`GENERATION_TIMEOUT_SECONDS=300`).

## 4. Avaliação contra o SLA de 5 minutos

- **Geração:** Q4_K_S 512×512/8 steps (~202 s) cabe com folga; 12 steps (~298 s)
  fica no limite. Recomendação: 512×512, 8 steps.
- **Edição:** 512×512/8 steps (~422 s) **não cabe** em 5 min. Com o timeout
  aprovado de 10 min, cabe. Se o SLA de 5 min for obrigatório, 448×448/8 steps
  (~291 s) é a alternativa, aceitando perda de qualidade; 384×384 (~216 s) é
  pior e não recomendado.

## 5. Risco térmico/energia

Durante um teste longo do Kontext, o PC **desligou sozinho**. A causa não foi
confirmada; a suspeita é térmica ou de energia (PSU). Antes de repetir testes
longos:

- monitorar temperatura de CPU/GPU e potência;
- garantir ventilação e PSU adequada;
- rodar uma execução curta (384×384) antes de 512×512;
- interromper imediatamente se houver throttling, cheiro, ruído anormal ou queda.

## 6. Recomendação para a integração

- **Geração:** FLUX.1 Dev **Q4_K_S**, 512×512, **8 steps**, difusão na GPU;
  T5/CLIP/VAE na CPU. Timeout 300 s.
- **Edição:** FLUX Kontext dev **Q4_0**, 512×512, **8 steps**, difusão na GPU;
  T5/CLIP/VAE na CPU. Timeout 600 s.
- **Q5_K_S:** não usar como padrão; não cabe inteiro no budget de 7,21 GiB e
  depende de offload parcial.
- **Q3_K_S:** fallback apenas se Q4 estourar memória.
- Sempre medir pico de VRAM com `GPU Adapter Memory > Dedicated Usage` e
  confirmar no Gerenciador de Tarefas; nunca usar `AdapterRAM` do WMI.
- O resumo manual não informa pico de RAM/VRAM nem flags exatas; a próxima
  execução deve registrá-los.
