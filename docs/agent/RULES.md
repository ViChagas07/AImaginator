# RULES — AImaginator

> Regras operacionais do agente neste repositório. Este arquivo é normativo:
> em caso de dúvida, ele vence preferências pessoais e exemplos antigos.

## 1. Arquitetura

- Monolito modular com Clean Architecture por módulo (`domain → application → adapters → infra`).
- Um módulo só pode importar de outro por `contracts.py`. Nunca importar `domain/` ou `adapters/` de outro módulo.
- `infra/settings.py` é o **único** arquivo autorizado a ler variáveis de ambiente. Não use `os.getenv` fora dele (exceto o helper `get_secret`, já existente e restrito a wiring).
- Regras de negócio vivem em `domain/`; casos de uso em `application/`; FastAPI, Celery, Redis, SQLAlchemy e SDKs externos ficam em `adapters/`/`infra/`/`apps/`/`workers/`.
- A API nunca expõe modelo ORM; schemas Pydantic são o contrato de transporte.
- Geração/edição nunca é síncrona no request HTTP: use a fila Celery e SSE.
- Não reintroduza a fila `generation.priority`: ela foi removida por ser código morto. A fila usada é `generation.standard`; a DLQ é `generation.dlq`.

## 2. Configuração

- Toda configuração nova entra em `infra/settings.py` e em `.env.example` (sem segredos reais).
- O `.env` da raiz está em modo `production` e **não** deve ser usado para desenvolvimento local. Use `.env.development` (copiado de `.env.development.example`).
- O usuário `RX 6500 XT` tem **8 GB de VRAM dedicada** (heap Vulkan `DEVICE_LOCAL` = 7,98 GiB; budget ~7,21 GiB). O valor de 4 GB do WMI `AdapterRAM` é um artefato de campo de 32 bits e **não deve ser usado**.
- Medição de pico de VRAM: `Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage'` antes/durante/depois, confirmando no Gerenciador de Tarefas (Desempenho → GPU → Memória de GPU dedicada). Nunca usar `AdapterRAM`.
- FLUX Q5_K_S (7,72 GiB) **não cabe inteiro** no budget de 7,21 GiB. A configuração recomendada é difusão na GPU + T5/CLIP/VAE na CPU; Q4_K_S/Q4_0 é o ponto de partida.

## 3. Segurança

- `PromptInjectionGuard` roda antes de classificador/escopo/LLM e antes de consumir cota.
- `PromptTopicGuard` (camada 1) e `ScopeGuardrail` (camada 2) são obrigatórios em geração e edição.
- A cota diária (`1` anônimo / `3` logado por 24h) só é consumida **depois** que o prompt passa por todos os guardrails. Prompt recusado não consome chance.
- `generation_credits` é um saldo persistido por usuário (default 50), verificado antes da cota diária e debitado depois dela; não substitui a cota diária. Anônimos não têm créditos, só a cota diária.
- URLs de imagem: `UrlPolicy` (HTTPS + allowlist + bloqueio de IP interno) e, quando houver fetch, `SecureImageFetcher` (DNS/redirect/bytes).
- Upload de imagem de edição: apenas PNG/JPEG, validação de tipo real por magic bytes, tamanho máximo configurável e dimensões válidas. Não processar a imagem sem um adapter de storage/modelo aprovado.
- Nunca logar segredos, tokens, DSNs ou prompts completos em produção.
- Nunca expor stack trace ao cliente; use o formato `{"error":{"code","message"}}`.

## 4. TDD e qualidade

- Escreva o teste antes ou junto da correção. Nenhuma correção sem teste.
- `pytest tests` e `pytest specs/evals -m eval` devem passar; no frontend, `npm run test -- --run` e `npm run test:e2e` devem passar.
- Não afrouxe guardrails para fazer teste passar. Ajuste a estratégia do teste quando o caso gerado for intencionalmente bloqueado.
- Testes de contrato devem cobrir os dois lados (backend e frontend) quando o payload muda.
- Não adicione dependências novas sem necessidade comprovada e sem atualizar `pyproject.toml`.

## 5. Decisões desta fase (Fase 2)

- `IMAGE_ENGINE` é `stub` por padrão. `sdcpp` é valor futuro; não integrar modelo nesta fase.
- Timeouts: geração 300 s; edição 600 s (aprovado porque Kontext 512×512 8 steps levou ~422 s). O SSE cobre o maior timeout + 60 s.
- Worker Celery: `--concurrency=1`, `--max-tasks-per-child=1`, `prefetch=1`.
- SSE: ao conectar, emitir o estado atual do banco; publicar `queued` na criação; não exibir posição na fila.
- Frontend: exibir `progress`, `result_image_url` e `error` do backend; usar `next_cursor`; mostrar a mensagem/código do backend com fallback localizado.
- Overlays “em breve” e o bloqueio de geração anônima foram removidos: o backend suporta geração anônima.
- Edição: contrato de upload multipart validado (PNG/JPEG, bytes, dimensões). O armazenamento e o runtime Kontext ficam para fase posterior.
- MinIO entra no compose de desenvolvimento apenas como infraestrutura; nenhuma integração de storage nesta fase.
- Portas de desenvolvimento: Postgres 5433, Redis 6380, RabbitMQ 5673/15673, API 8001, MinIO 9002/9003 (evitando a stack ForjaB2B).
- Risco térmico: o PC desligou durante um teste longo do Kontext. Monitore temperatura/energia antes de repetir execuções longas.

## 6. Decisões da Fase 3

- `IMAGE_ENGINE=sdcpp` usa `SdCppImageGenerator`/`SdCppImageEditor`; o
  orquestrador escolhe a porta pelo `kind` da `Generation`.
- PROIBIDO executar o sd-cli real em teste, CI ou comando do agente. Todos os
  testes usam `tests/fakes/fake_sd_cli.py` (executável falso).
- `subprocess` sempre com lista de argumentos; nunca `shell=True`. Timeout
  mata a árvore de processos (`taskkill /T /F` no Windows, grupo POSIX).
- Erros de motor são estáveis e seguros: `engine_timeout`, `engine_oom`,
  `engine_failed`, `insufficient_resources`, `invalid_dimensions`. Saída bruta
  e caminhos ficam só no log interno do worker.
- Storage S3/MinIO: resultados em `generations/{id}/result.png`, origens em
  `sources/{id}/source.png`; respostas usam URL assinada, nunca credenciais.
  `S3_SOURCE_RETENTION_HOURS` controla a limpeza das origens de edição.
- Upload de edição cria a `Generation` e enfileira; a variante por URL baixa
  via `SecureImageFetcher` e valida tipo/tamanho/dimensões antes de enfileirar.
- Seed opcional é devolvida nos metadados e persistida em `generations.seed`.
- A pós-produção do orquestrador valida os bytes (PNG/JPEG + dimensões) antes
  do upload e expõe uma lista de pós-processadores para marca d'água e
  moderação futuras.

## 7. Assistente de prompts e moderação (Fase 4)

- O produto só devolve imagem ou recusa padronizada. O assistente nunca
  conversa, responde perguntas ou executa tarefas fora de imagem.
- O LLM local (`PromptAssistant`, Qwen via LM Studio) roda NO WORKER, depois
  das guardas determinísticas da requisição e ANTES do FLUX/Kontext. O worker
  tem concorrência 1: uma chamada por job, nunca simultânea ao motor.
- `PromptInjectionGuard` e `ScopeGuardrail` são a primeira camada
  determinística. A normalização anti-injeção cobre Unicode NFKC, zero-width,
  leetspeak básico e padrões em 11 idiomas.
- Texto do usuário é sempre DADO entre delimitadores; o system prompt é em
  inglês e proíbe revelar instruções, mudar de papel ou produzir texto fora
  do JSON.
- Bloqueios: sexual/NSFW (menores = absoluto), gore, ódio e autolesão.
  Copyright (personagens/marcas) é PERMITIDO. Conteúdo educativo/artístico
  não explícito (anatomia, nu clássico, guerra histórica sem gore, comida crua)
  deve passar.
- Decisão de bloqueio é em código: categoria com confiança >=
  `LLM_BLOCK_CONFIDENCE`; escopo falso ou não-imagem recusa; JSON inválido
  após UM reparo = `assistant_unavailable` (fail-closed).
- Mensagens de recusa/aviso são localizadas pelo locale do SITE (X-Locale >
  Accept-Language > pt-BR), nunca pelo idioma detectado no prompt. Catálogo
  backend cobre 11 locales; autolesão inclui apoio genérico e gentil.
- Texto de prompt NUNCA vai para logs. `moderation_events` guarda SHA-256 e
  comprimento; `MODERATION_STORE_PROMPT_TEXT=true` (default false) trunca em
  200 caracteres.
- Penalidades por 24h: 3 = aviso, 5 = bloqueio de 1h, 10 = revisão + bloqueio
  de 24h (`users.moderation_flag`). Escopo e injeção não contam penalidade.
- Recusa do LLM ou falha do motor devolvem a chance diária (release atômico no
  Redis); o flag `generations.quota_refunded` evita devolução dupla.
- Em testes, o LLM é SEMPRE falso (`tests/fakes/llm.py`). Evals reais ficam em
  `specs/evals` e só rodam com `RUN_LLM_EVALS=1`; o agente não as executa.

## 8. Estúdio, i18n e créditos (Fase 5)

- Interface completa em 11 locales: pt-BR, en, es, fr, de, it, ja, zh, ko, ru,
  ar. Todo texto visível vem de `messages/*.json`; placeholders devem ser
  idênticos entre locales. Árabe usa `dir="rtl"` e propriedades lógicas.
- Fontes Noto (JP/SC/KR/Arabic) via `next/font`; latim permanece Geist.
- Metadados/SEO são gerados por locale a partir das mensagens (`title`,
  `description`, `openGraph.locale`).
- Seed é opcional, inteiro de 0 a 2^32-1; proporção é um enum das cinco
  canônicas. Valores inválidos retornam `invalid_input` (422, localizado).
- Variação: mesmo prompt/proporção/estilo e seed nova; passa por guardrails,
  cota, penalidades e assistente. Só o dono (ou a própria sessão anônima).
- Refinar: `source_generation_id` exige geração DONE e do solicitante; o
  worker lê o resultado do S3 e grava `parent_generation_id`. Edição/refino
  exigem login; anônimo continua podendo gerar e variar.
- Histórico devolve prompt original, kind, proporção, seed, status, URL
  assinada e `parent_generation_id`, paginado por `next_cursor`.
- Créditos: recusa do LLM, `assistant_unavailable`, falha do motor e recusa de
  moderação devolvem `generation_credits` (regra escolhida: devolver sempre,
  pois a penalidade já pune o abuso). A devolução é idempotente por geração
  (`generations.credits_refunded`); a chance diária usa `quota_refunded`.
- A UI nunca mostra posição na fila; mostra apenas progresso SSE, estimativa
  de tempo e mensagens localizadas do backend.

## 9. Saída protegida: imagem, marca, metadados e upscale (Fase 6)

- Ordem obrigatória para geração/edição/variação/refino: decodificar/validar
  bytes -> moderar a imagem gerada -> gravar `generations/{id}/original.png`
  (privado) -> marca d'água -> metadados de IA -> gravar
  `generations/{id}/result.png` -> publicar. Progresso 90–99%.
- `original_object_key` NUNCA aparece em API/SSE/galeria/histórico. Só a
  versão com marca é servida por URL assinada. Refino e upscale leem o
  original privado, nunca o resultado público.
- Origem enviada para edição (`sources/{id}/source.png`) é moderada no worker
  após o assistente e antes do motor. Bloqueio apaga a origem e CONTA
  penalidade (`layer=image_input`). Bloqueio da imagem gerada não conta
  penalidade (`layer=image_output`), mas registra evento e devolve crédito.
- `IMAGE_MODERATOR=local` usa NSFW + CLIP carregados sob demanda e liberados
  após o job. Dependências pesadas ficam no grupo opcional `moderation`;
  sem elas o adapter falha fechado (`image_moderation_unavailable`).
- Marca d'água é obrigatória em todas as imagens servidas, inclusive upscale,
  via `WATERMARK_*`; o asset precisa existir e ter alfa (validado no startup).
- Metadados: `DigitalSourceType=trainedAlgorithmicMedia`, gerador
  AImaginator, modelo e data UTC em tEXt/iTXt + XMP/IPTC. Nunca prompt, seed,
  usuário ou e-mail. C2PA é opcional e falha apenas com aviso.
- Upscale é `kind=upscale`, exige login/dono/DONE, usa original privado, não
  passa pelo assistente nem repete moderação e NÃO consome cota de prompts.
  Limite próprio `UPSCALE_DAILY_LIMIT` (24h), liberado em falha do motor.
  Motores: `lanczos` (Pillow) ou `esrgan` (sd-cli com timeout/kill/limpeza).

## 10. Observabilidade e métricas (Fase 7)

- Métricas nunca recebem prompt, e-mail, IP em claro, IDs de usuário/geração,
  chaves S3 ou URLs assinadas. Só labels de baixa cardinalidade.
- Worker com `--max-tasks-per-child=1` exige modo multiprocesso do
  prometheus_client: `PROMETHEUS_MULTIPROC_DIR` é configurado antes de criar
  metrics, limpo no `worker_init`, e o processo principal expõe o endpoint
  agregado em `WORKER_METRICS_PORT`.
- Toda etapa usa `stage_timer` (duração + log estruturado) e correlação por
  geração (`correlation_id` = id da geração) em logs, nunca em metric label.
- `/readyz` bloqueia apenas dependências reais; LM Studio é aviso.
- Sentry backend/frontend scrubam mensagens, breadcrumbs, request, extras,
  tags e contextos. DSN vazio desliga a integração.
- Scripts `tools/smoke_*` e `tools/run_evals_report.py` são manuais. Nunca
  executá-los em CI/teste do agente; eles podem carregar modelos reais.

## 11. Git

- Não fazer commit nem push sem pedido explícito.
- Nunca commitar `.env`, modelos, binários, saídas de teste, `tools/flux-spike/bin`, `tools/flux-spike/out` ou artefatos de runtime.
