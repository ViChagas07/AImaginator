# Spec: GenerateImageFromPrompt

> Status: implementado · Módulo: `modules/image_generation`

## Intenção

Como usuário autenticado, quero gerar uma imagem nova a partir de um prompt
em linguagem natural e acompanhar o progresso em tempo real.

## Pré-condições

- Usuário autenticado (sessão OIDC válida — módulo `auth`).
- Usuário possui cota de geração disponível (`User.generation_credits > 0`).
- Provedor de imagem configurado (`AI_IMAGE_PROVIDER`, `stub` em dev/teste).

## Contrato de entrada (porta)

`POST /api/v1/generations` — `GenerateImageInput`

| Campo            | Tipo            | Regras                                   |
| ---------------- | --------------- | ---------------------------------------- |
| `prompt`         | `str`           | 1..2000 chars, sanitizado anti-injection |
| `negative_prompt`| `str \| null`   | opcional, 0..2000 chars                  |
| `style_preset`   | `StylePreset`   | enum opcional (default `none`)           |
| `aspect_ratio`   | `AspectRatio`   | enum opcional (default `1:1`)            |

## Contrato de saída (porta)

`202 Accepted` — `GenerationOutput`

| Campo            | Tipo     | Descrição                                  |
| ---------------- | -------- | ------------------------------------------ |
| `id`             | `UUID`   | identificador da geração                   |
| `status`         | enum     | `queued \| processing \| done \| failed`   |
| `stream_url`     | `str`    | endpoint SSE para acompanhar o progresso   |

## Regras de negócio

- O prompt passa pela `PromptInjectionGuard` (domain) **antes** de qualquer
  agente de IA (defesa em profundidade — spec seção 7).
- A cota é debitada na entidade `User.consume_credit()`; estourou → 429.
- A geração é **enfileirada no Celery** (`TaskQueuePort`), nunca processada
  de forma síncrona no request HTTP — a API responde 202 imediatamente.
- O progresso é publicado no Redis Pub/Sub e repassado via SSE.

## Casos de erro

| Cenário                          | Código HTTP | Motivo                                      |
| -------------------------------- | ----------- | ------------------------------------------- |
| Prompt vazio/malicioso           | 422         | `prompt_rejected` (anti prompt-injection)   |
| Prompt acima do limite           | 422         | `prompt_rejected`                           |
| Cota excedida                    | 429         | `quota_exceeded`                            |
| Rate limit por usuário           | 429         | `rate_limit_exceeded` + `Retry-After`       |
| Não autenticado                  | 401         | `unauthorized`                              |

## Testes (TDD) obrigatórios

- [x] Guarda rejeita vetores de injection (parametrizado + property-based).
- [x] Guarda aceita prompts legítimos dentro do limite.
- [x] Caso de uso debita cota e enfileira a task (`SpyTaskQueue`).
- [x] Cota esgotada → `QuotaExceededError`.
- [x] API retorna 202 + `stream_url`; 422 em injection; 401 sem auth.

## Evals (EDD) obrigatórios

- [x] `safety_refusal`: 100% dos prompts maliciosos recusados.
- [x] `output_validity`: output é URL `https` válida.
- [x] `progress_monotonic`: progresso nunca regride.
- [x] `latency_sla`: pipeline (stub) abaixo do SLA.

## Implementação

- `modules/image_generation/application/use_cases/generate_image.py`
- `modules/image_generation/domain/prompt_guard.py`
- `modules/image_generation/domain/entities.py` (máquina de estados)
- `apps/api/routers/generations.py` (`POST /generations`)
