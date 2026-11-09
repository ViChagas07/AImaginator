# PROGRESS — AImaginator

> Atualizado ao final de cada bloco. Status: `pendente`, `em andamento`, `concluído`, `bloqueado`.

## Fase 0 — Diagnóstico

- [x] Relatório em `docs/agent/FASE0_REPORT.md`.
- [x] VRAM real corrigida: ~8 GB dedicados (Vulkan `DEVICE_LOCAL` 7,98 GiB; dxdiag 8146 MB); WMI `AdapterRAM` de 4 GB descartado.

## Fase 1 — Spike local

- [x] Resultados manuais registrados em `docs/agent/FASE1_SPIKE.md`.
- [x] Runtime de referência: stable-diffusion.cpp Vulkan `sd-master-37bc88b`.
- [x] Decisão: geração Q4_K_S 512×512/8 steps ~202 s; edição Kontext Q4_0 512×512/8 steps ~422 s, com timeout de 600 s aprovado.

## Fase 2 — Fundação

### Bloco 1 — Documentação do agente

- [x] `docs/agent/RULES.md`.
- [x] `docs/agent/PROGRESS.md`.
- [x] `docs/agent/FASE1_SPIKE.md` com os resultados medidos manualmente.

### Bloco 2 — Configuração por variáveis de ambiente

- [x] `infra/settings.py` com `IMAGE_ENGINE`, caminhos SDCPP, dimensões/steps/guidance, timeouts e limites de upload.
- [x] Constantes de proporção no domínio (`AspectRatio.FOUR_THREE`, `ASPECT_RATIO_DIMENSIONS`).
- [x] `.env.example` atualizado sem segredos.
- [x] Testes de settings (`11 passed` com os testes de proporção).

### Bloco 3 — Ambiente local de desenvolvimento

- [x] `.env.development.example` com localhost e portas alternativas.
- [x] Compose de desenvolvimento com portas 5433/6380/5673/15673/8001 e MinIO.
- [x] README com instruções de API, worker e frontend em dev.
- [x] `.env.development` adicionado ao `.gitignore`.

### Bloco 4 — Fila e timeouts

- [x] Worker com `concurrency=1`, `max-tasks-per-child=1`, prefetch 1.
- [x] Limites soft/hard por `kind` (generate/edit): `270/300` e `570/600`.
- [x] SSE com timeout dinâmico (maior timeout + 60 s = 660 s).
- [x] Fila `generation.priority` removida (documentado).
- [x] Testes de seleção de limites por kind (`8 passed`, incluindo o adapter Celery).

### Bloco 5 — Contratos backend × frontend

- [x] SSE: frontend lê `progress`, `result_image_url` e `error`.
- [x] Histórico: frontend lê `next_cursor`.
- [x] Erros HTTP: frontend usa `error.message`/`error.code` com fallback localizado.
- [x] Contrato de upload de edição (`POST /generations/edits/upload`) com validação PNG/JPEG, bytes e dimensões; helpers no frontend.
- [x] Overlays “em breve” e bloqueio de geração anônima removidos.
- [x] Testes de contrato no backend e frontend.

### Bloco 6 — SSE resiliente

- [x] Estado inicial do banco ao conectar (`stream_events.py`).
- [x] Evento `queued` publicado na criação (generate anônimo/autenticado e edit).
- [x] Testes: conexão após término, durante processamento, falha, geração inexistente e payload (`7 passed`).
- [x] Sem posição na fila.

### Bloco 7 — Cota e limites

- [x] Cota consumida depois dos guardrails (injeção, escopo e URL).
- [x] Cota diária aplicada a edições.
- [x] Relação `generation_credits` × cota diária documentada em `RULES.md`.
- [x] Testes da ordem, de recusa sem consumo e de edição (`13 use case + 25 API`).

### Bloco 8 — Suíte verde

- [x] Teste property-based filtrado para palavras bloqueadas por design (a guarda não foi afrouxada).
- [x] `pytest tests` verde: **167 passed, 1 skipped**.
- [x] `pytest specs/evals -m eval` verde: **4 passed**.
- [x] `npm run test -- --run` verde: **21 passed**.
- [x] `npm run test:e2e` verde: **5 passed**.
- [x] `npm run lint`: 0 errors (2 warnings pré-existentes em `auth-ui.tsx`).
- [x] `npx tsc --noEmit`: sem erros.

## Resultado final da Fase 2

- Backend: `167 passed, 1 skipped` (`tests`); `4 passed` (`specs/evals`).
- Frontend: `21 passed` (vitest); `5 passed` (Playwright); lint sem erros; typecheck limpo.
- Nenhum commit/push realizado.
- `IMAGE_ENGINE=sdcpp` permanece sem implementação real; o wiring falha explicitamente para evitar fallback silencioso.
- A cota diária agora é consumida somente após injeção, escopo e URL; aplica-se a geração e edição.
- O upload de edição valida bytes reais (PNG/JPEG), tamanho e dimensões, mas ainda não persiste nem processa a imagem.

## Fase 3 — Adapters FLUX/Kontext + storage S3

### Bloco 1 — Portas

- [x] `ImageGeneratorPort` e `ImageEditorPort` separadas, devolvendo bytes +
  metadados (`width`, `height`, `seed`, `duration_seconds`).
- [x] Orquestrador escolhe gerador/editor pelo `kind` da `Generation`.
- [x] `StubImageProvider` legado preservado para testes; stubs novos também
  devolvem PNG válido.
- [x] Erros de domínio: `engine_timeout`, `engine_oom`, `engine_failed`,
  `insufficient_resources`, `invalid_dimensions`, `storage_unavailable`.

### Bloco 2 — Adapter sdcpp

- [x] `build_sdcpp_command` puro, argv em lista, paths com espaços suportados.
- [x] `SdCppImageGenerator`/`SdCppImageEditor` com `asyncio.create_subprocess_exec`.
- [x] Timeout por kind; kill da árvore (`taskkill /T /F` / grupo POSIX).
- [x] Parser de progresso real (`| 3/8 - 19.5s/it`) mapeado para 10–90%.
- [x] OOM/saída inválida/arquivo ausente mapeados; log completo só no interno.
- [x] Temp dir limpo em `finally` (inclusive timeout).
- [x] Guarda `MIN_FREE_RAM_MB` via psutil e `COOLDOWN_SECONDS_BETWEEN_JOBS`.
- [x] Seed opcional devolvida; proporções canônicas validadas.

### Bloco 3 — Storage S3

- [x] `ObjectStoragePort` + `S3ObjectStorage` (boto3 em `asyncio.to_thread`).
- [x] Settings S3 e exemplos de env (MinIO 9002/9003); `S3_PUBLIC_ENDPOINT_URL`
  separa o endpoint interno do host usado nas URLs assinadas.
- [x] Migration `20261106_120000`: `result_object_key`, `source_object_key`,
  `seed`, `error_code`.
- [x] Bucket criado automaticamente em desenvolvimento.
- [x] URLs assinadas no SSE, histórico e galeria.
- [x] Retenção configurável das origens (`S3_SOURCE_RETENTION_HOURS`) com
  limpeza oportunista após edições e task periódica opcional.
- [x] Testes com fake + integração MinIO opcional (`RUN_S3_TESTS=1`).

### Bloco 4 — Fluxo de edição

- [x] `POST /generations/edits/upload` valida, grava `sources/{id}/source.png`,
  cria `Generation(kind=edit)` e enfileira (202).
- [x] Variante `source_image_url` baixa via `SecureImageFetcher`, valida
  tipo/tamanho/dimensões e grava no S3.
- [x] Worker baixa a origem do S3 e executa o editor.

### Bloco 5 — Orquestrador e wiring

- [x] `_generate_or_edit` usa as portas novas e callback de progresso real.
- [x] `_post_process` valida PNG/JPEG + dimensões antes do upload.
- [x] Lista explícita de pós-processadores para marca d'água/moderação futuras.
- [x] Wiring `sdcpp` exige caminhos e S3 no startup; `stub` continua funcionando.
- [x] Falhas viram `FAILED` com código estável e mensagem segura; SSE publica
  `error` + `error_code`.

### Bloco 6 — Smoke test manual

- [x] `tools/smoke_sdcpp.py` criado (não executado): RAM antes/depois, tempos,
  aviso térmico, `--edit --source`.

### Bloco 7 — Testes e entrega

- [x] Testes de comando, parser, erros, timeout/kill, limpeza, RAM, proporções,
  seleção por kind, storage fake e orquestrador.
- [x] Documentação de como ligar `sdcpp`, variáveis e smoke test no README.

## Resultado final da Fase 3

- Backend: `pytest tests` verde — **205 passed, 2 skipped** (integrações
  opcionais de MinIO/Postgres).
- Evals: `pytest specs/evals -m eval` verde — **4 passed**.
- Frontend: vitest **22 passed**, lint sem erros, `tsc --noEmit` limpo e
  Playwright **5 passed**.
- Nenhum commit/push realizado.
- Nenhuma execução real de FLUX/Kontext em testes/comandos.

## Fase 4 — Assistente multilíngue, moderação e penalidades

### Bloco 1 — Cliente LLM

- [x] Porta `LlmClientPort` + adapter HTTP OpenAI-compatible (LM Studio).
- [x] Settings `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`,
  `LLM_TIMEOUT_SECONDS`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_TTL_SECONDS`,
  `PROMPT_MAX_CHARS`.
- [x] `temperature=0`, `response_format` json_schema, `ttl` e desativação de
  raciocínio com fallback em HTTP 400/422 quando o servidor não aceita campos.
- [x] `<think>` removido, parse tolerante, UM reparo e fail-closed.

### Bloco 2 — PromptAssistant

- [x] Serviço/porta com uma chamada estruturada: idioma, escopo, moderação,
  confiança, parte de imagem, correção, `flux_prompt`/`kontext_instruction` e
  `suggested_aspect_ratio` validado.
- [x] System prompt em inglês, texto do usuário entre delimitadores, regras
  anti-injeção e proibição de conversar.
- [x] Regras de decisão em código (confiança mínima, escopo, fail-closed).
- [x] Assistente roda no worker antes do motor e publica progresso 7–10%.
- [x] Limites soft/hard da task e do SSE agora cobrem LLM + motor + margem,
  sem alterar o timeout do subprocesso do sd-cli.
- [x] FLUX recebe `flux_prompt`; Kontext recebe `kontext_instruction`; prompt
  original permanece na `Generation`.
- [x] Guarda determinística na requisição com normalização NFKC/zero-width/
  leetspeak e injeções em pt, en, es, fr, de, it, ja, zh, ko, ru, ar.

### Bloco 3 — Recusas localizadas

- [x] Catálogo backend nos 11 locales: nsfw, gore, hate, self_harm,
  out_of_scope, prompt_rejected, assistant_unavailable, temporarily_blocked,
  warning_level_1 e account_under_review. Autolesão inclui apoio gentil.
- [x] X-Locale > Accept-Language > pt-BR, validado; locale salvo na Generation.
- [x] SSE entrega `message`, `error_code`, `warning_level` e
  `warning_message`; HTTP entrega o mesmo no envelope `error`.
- [x] CORS libera `X-Locale`.
- [x] Teste garante todas as chaves nos 11 locales, não vazias e não copiadas
  do pt-BR (exceto en/pt-BR).

### Bloco 4 — Cota e penalidades

- [x] `release` atômico no store Redis + `RefundPromptQuota`; worker devolve a
  chance em recusa do LLM e falha do motor, com `generations.quota_refunded`
  para evitar dupla devolução.
- [x] Tabela `moderation_events` (migration) com SHA-256/comprimento, sem
  texto por padrão; flag opcional trunca em 200.
- [x] Penalidades 3/5/10 na janela 24h, bloqueio 1h, revisão 24h e
  `users.moderation_flag`; anônimo por sessão + ip_hash.
- [x] HTTP 429 `temporarily_blocked` com tempo restante; métrica Prometheus
  por categoria/camada; log estruturado no nível 3. Penalidade vale para
  geração e edição.

### Bloco 5 — Frontend mínimo

- [x] `X-Locale` nas requisições de geração e no stream SSE.
- [x] Mensagem localizada de recusa e aviso de nível 1 exibidos; 429 mostra a
  mensagem do backend. Sem posição na fila.

### Bloco 6 — Testes e evals

- [x] Testes com LLM falso: JSON válido/inválido, reparo, think, timeout,
  categorias, limiar, escopo, prompt misto, injeção, refund, penalidades,
  janela 24h e locale inválido.
- [x] Evals multilíngues em `specs/evals` (11 idiomas, bloqueios, copyright,
  escopo, injeção e limítrofes), marcadas e gated por `RUN_LLM_EVALS=1`.
- [x] Documentação de política, variáveis e evals reais no README/RULES.

## Resultado final da Fase 4

- Backend: `pytest tests` verde — **276 passed, 2 skipped**.
- Evals automáticas: **4 passed, 1 skipped** (a eval real do LLM é pulada).
- Frontend: vitest **23 passed**, lint sem erros, `tsc --noEmit` limpo.
- Nenhum teste/carrega o Qwen/LM Studio real; nenhuma eval real executada.
- Nenhum commit/push realizado.

## Fase 5 — i18n 11 idiomas + estúdio + créditos

### Bloco 1 — i18n completo

- [x] 11 locales em routing, seletor, settings, middleware e carregamento:
  pt-BR, en, es, fr, de, it, ja, zh, ko, ru, ar.
- [x] 344 chaves em todos os arquivos, com placeholders idênticos, sem vazios.
- [x] It e Ko completos; 150 chaves antes faltantes preenchidas nos 7 locales.
- [x] Árabe com `dir="rtl"`, propriedades lógicas no estúdio/galeria/menu.
- [x] Fontes Noto JP/SC/KR/Arabic via next/font + stacks de fallback.
- [x] Metadados/SEO por locale (`title`, `description`, `openGraph.locale`,
  hreflang) e `lang` correto. README atualizado.

### Bloco 2 — backend da interface

- [x] `GenerateImageInput.seed` (0..2^32-1) e validação de proporção com
  `invalid_input` 422 localizado; seed salva e devolvida no SSE/histórico.
- [x] `POST /generations/{id}/variations`: mesmo prompt/proporção, seed nova,
  guardrails/cota/penalidades/assistente, dono ou própria sessão anônima.
- [x] Refino com `source_generation_id`: valida dono + DONE, lê o resultado do
  S3, grava `parent_generation_id` (migration 20261106_140000).
- [x] Histórico devolve seed e `parent_generation_id` além dos campos já
  existentes; paginação `next_cursor` preservada.
- [x] Créditos devolvidos em recusa do LLM, `assistant_unavailable`, falha do
  motor e moderação; idempotente via `credits_refunded` (teste de dupla
  devolução). Regra documentada em RULES.
- [x] Edição/refino continuam exigindo login; anônimo gera e varia.

### Bloco 3 — interface do estúdio

- [x] Seletor de 5 proporções com rótulos traduzidos, preview e seed avançada
  colapsável.
- [x] Abas Gerar/Editar; anônimo vê edição desabilitada com CTA de login.
- [x] Upload PNG/JPEG por drag-and-drop/seletor, preview e validação de
  tipo/tamanho/dimensões no cliente.
- [x] Resultado com Baixar, Gerar variação e Refinar (instrução encadeada).
- [x] Progresso SSE real + estimativa traduzida; sem posição na fila.
- [x] Histórico paginado com miniaturas, prompt, data, ações e cadeia parent.
- [x] Recusas/avisos localizados do backend exibidos; layout responsivo,
  acessível e com propriedades lógicas/RTL.

### Bloco 4 — testes e entrega

- [x] Backend: seed, variação, refino, histórico, validação e dupla devolução
  de crédito cobertos.
- [x] Frontend: contrato, validação de upload, store e paridade dos 11 locales.
- [x] Playwright mockado: proporção/seed/progresso, variação, refino, upload
  inválido/válido, recusa localizada, anônimo sem edição, ar/ja/ko/it.
- [x] README/RULES/PROGRESS atualizados. Build de produção do frontend OK.

## Resultado final da Fase 5

- Backend: `pytest tests` verde — **296 passed, 2 skipped**.
- Evals automáticas: **4 passed, 1 skipped** (LLM real continua gated).
- Frontend: vitest **39 passed**; Playwright **12 passed**; lint sem erros;
  `tsc --noEmit` limpo; `next build` concluído (118 páginas).
- Nenhum commit/push; nenhum modelo real executado.

## Fase 6 — moderação de imagem, marca d'água, metadados e upscale

### Bloco 1 — pipeline

- [x] Ordem: validação -> moderação da saída -> `original.png` privado ->
  marca d'água -> metadados -> `result.png` público -> SSE (90–99%).
- [x] `original_object_key` + migration; a chave privada não é exposta.
- [x] Refino e upscale leem o original limpo; resultado público nunca é fonte.

### Bloco 2 — moderação de imagem

- [x] `ImageModeratorPort`, fake, adapter local NSFW+CLIP lazy/liberado por job
  e fail-closed (`image_moderation_unavailable`).
- [x] Origem de edição moderada no worker após o assistente; bloqueio apaga
  S3, devolve crédito/cota e conta penalidade (`image_input`).
- [x] Saída bloqueada não grava nada, devolve crédito, registra evento
  (`image_output`) sem contar 3/5/10.
- [x] Mensagens localizadas nos 11 locales e métrica Prometheus por
  categoria/camada.

### Bloco 3 — marca d'água

- [x] Asset copiado para o backend, validado no startup (PNG com alfa).
- [x] Logo proporcional, mínimo, margem, opacidade, sombra, Lanczos e cache
  por tamanho; aplicada em geração/edição/variação/refino/upscale.
- [x] Testes de geometria, alfa, todas as proporções e upscale.

### Bloco 4 — metadados de IA

- [x] tEXt/iTXt + XMP/IPTC com DigitalSourceType, gerador, modelo e data UTC.
- [x] Sem prompt/seed/usuário/e-mail.
- [x] C2PA opcional atrás de `C2PA_ENABLED`; ausência de lib/certificado só
  gera aviso.

### Bloco 5 — upscale

- [x] `kind=upscale`, endpoint autenticado, dono DONE, original privado.
- [x] Lanczos e ESRGAN (sd-cli com timeout/kill/limpeza/guarda de RAM).
- [x] Limite próprio de 5/24h, liberado em falha; sem cota de prompts,
  assistente ou nova moderação.
- [x] Timeouts por kind na fila/SSE; marca/metadados no novo tamanho.

### Bloco 6/7 — frontend e testes

- [x] Botão Ampliar no resultado/histórico, progresso SSE e limite restante.
- [x] Mensagens de imagem localizadas exibidas; download sempre público.
- [x] Suíte sem o grupo opcional `moderation`.

## Resultado final da Fase 6

- Backend: `pytest tests` verde — **341 passed, 2 skipped** (após testes de
  limites de upscale).
- Evals automáticas: **4 passed, 1 skipped**.
- Frontend: vitest **40 passed**; Playwright **13 passed**; lint/tsc limpos;
  `next build` OK.
- Nenhum peso/modelo real foi baixado ou executado; nenhum commit/push.

## Fase 7 — métricas, observabilidade e scripts de validação

### Bloco 1 — Prometheus multiprocesso

- [x] `PROMETHEUS_MULTIPROC_DIR` lido por settings e configurado antes das
  métricas; worker limpa o diretório no `worker_init`.
- [x] Endpoint HTTP do processo principal do worker em `WORKER_METRICS_PORT`
  (9100) com `MultiProcessCollector`; API `/metrics` compatível.
- [x] Scrape `worker:9100` e regras em `infra/docker/prometheus/alerts.yml`.
- [x] Teste de filho encerrado aparecendo no endpoint agregado.

### Bloco 2 — métricas do pipeline

- [x] Gerações por kind/status, duração, etapas (input_guard, assistant_llm,
  input/output moderation, engine, watermark_metadata, upload, upscale).
- [x] LLM: outcome, latência e reparos de JSON.
- [x] Moderação/recusas, falhas do motor por motivo, RAM livre/pico do
  subprocesso, créditos/cota devolvidos, penalidades, upscale, fila, SSE e
  rate limit.
- [x] Testes de nome/tipo/labels, baixa cardinalidade, fila e cronômetro.

### Bloco 3 — logs e correlação

- [x] `correlation_id` por geração no request, task, etapa e logs structlog;
  nunca como label de métrica.
- [x] Falhas registram tipo/código, sem payload bruto.
- [x] Teste de scrubbing de logs com prompt proposital.

### Bloco 4 — saúde e alertas

- [x] `/readyz` verifica Postgres, Redis, RabbitMQ, S3, arquivos do sdcpp e
  LM Studio como aviso não bloqueante.
- [x] Regras de alerta versionadas para falha do motor, timeout, fila parada,
  recusa anormal, LLM e upload.

### Bloco 5 — Sentry

- [x] Backend: scrubber ampliado para mensagens, breadcrumbs, request,
  extras/tags/contextos, e-mail, IP, tokens e URLs assinadas.
- [x] Frontend: `@sentry/nextjs` com DSN opcional, amostragem baixa e
  scrubbing equivalente (`instrumentation.ts`/client).
- [x] Testes dos scrubbers backend e frontend.

### Bloco 6 — Grafana

- [x] `api-health.json` usando apenas métricas reais.
- [x] Novo dashboard `pipeline.json` com gerações, etapas, recusas, motor,
  LLM, fila, RAM, créditos, penalidades e upscale.
- [x] Validação de JSON e métricas referenciadas em teste.

### Bloco 7 — scripts manuais

- [x] `tools/smoke_assistant.py`, `tools/smoke_moderation.py` e
  `tools/run_evals_report.py` criados (NÃO executados).
- [x] `specs/evals` reutilizável gera `docs/agent/EVALS_REPORT.md` com
  acurácia por categoria/idioma, falsos bloqueios/passes e latência.
- [x] README documenta ordem, RAM/temperatura e VRAM via HWiNFO/Adrenalin.

## Resultado final da Fase 7

- Backend: **359 passed, 2 skipped**.
- Evals automáticas: **4 passed, 1 skipped**.
- Frontend: vitest **43 passed**; Playwright **13 passed**; lint/tsc limpos;
  `next build` OK.
- Ruff: sem erros nos arquivos da fase.
- Nenhum modelo real, script manual ou eval real foi executado.
- Nenhum commit/push.

## Fase 8 — segurança, E2E, limpeza, documentação e entrega

### Bloco 1 — revisão de segurança

- [x] IDOR revisado em detalhe/histórico/galeria/variação/refino/upscale/
  stream; testes de ownership e `original_object_key` nunca exposto.
- [x] JWT removido da URL do SSE: ticket single-use em Redis (TTL 60s),
  vinculado à geração e ao solicitante; frontend usa ticket.
- [x] sd-cli: prompt sanitizado (controle/quebras, limite 2000, prefixo para
  `-`), argv em lista sem shell e teste com executável falso registrando argv.
- [x] Upload: `Image.MAX_IMAGE_PIXELS`, limite de pixels, `verify()`, reencode
  PNG sem EXIF/metadados, temp dirs aleatórios/permissão mínima no POSIX.
- [x] TokenBucket usa Redis TIME; teste com relógio monotônico local divergente.
- [x] CORS restrito, CSP/headers Next+API, HSTS em produção, SSRF revisado.
- [x] Dependências: pip-audit limpo; `npm audit --omit=dev` limpo; resíduos de
  dev documentados em `docs/agent/SECURITY_REVIEW.md`.

### Bloco 2 — feature flag e produção

- [x] `FEATURE_IMAGE_GENERATION_ENABLED` (false em produção por padrão),
  `feature_disabled` 503 localizado nos 11 locales, `/api/v1/config`.
- [x] Validação de sdcpp/S3/LLM/watermark só com a flag ligada; produção sobe
  desligada.
- [x] `original_unavailable` (409) localizado em refino/upscale antigos.
- [x] Migrations aditivas com downgrade; teste de inspeção.

### Bloco 3 — E2E de infraestrutura

- [x] `tests/integration/test_e2e_infra.py` (RUN_E2E_INFRA=1) cobre geração,
  edição/upload, refino, variação, upscale, URLs assinadas, marca/metadados e
  caminhos de recusa/limite. Pulado por padrão; não executado nesta fase.

### Bloco 4 — CI

- [x] `.github/workflows/ci.yml` com backend lint/test/eval, auditorias
  informativas, frontend lint/tsc/vitest/build e Playwright mockado, sem
  segredos. Workflow antigo em `infra/github` removido.

### Bloco 5 — limpeza

- [x] `.gitignore` cobre `.env*` com exceções de examples, modelos, saídas,
  imagens de teste, logs, caches e node_modules.
- [x] Stub `IMAGE_ENGINE=stub` preservado; validador de upload morto removido.
- [x] README atualizado (estado real, feature flag, CI, licenças, avisos) e
  ADRs em `docs/agent/adr/`.

### Blocos 6/7 — varredura e testes finais

- [x] Varredura de segredos/arquivos grandes e histórico local.
- [x] Backend **380 passed, 4 skipped**; evals **4 passed, 1 skipped**;
  vitest **43 passed**; Playwright **14 passed**; ruff/tsc/lint/build verdes.
- [x] `docs/agent/{SECURITY_REVIEW,FINAL_REPORT,MANUAL_VALIDATION}.md`.

## Fase 7.5 - correcao do LLM local, fila orfa, dev e logs

### Bloco 1 - cliente LLM

- [x] `chat_template_kwargs` removido; `reasoning_effort` no topo, configuravel
  por `LLM_REASONING_EFFORT` (default `none`, vazio = nao envia).
- [x] Fallback 400/422 remove `response_format`, depois `reasoning_effort` e,
  por fim, todos os campos opcionais.
- [x] Saida `finish_reason=length` sem `content` vira `llm_output_truncated`
  (metrica `outcome=truncated`) e tenta UMA vez com `reasoning_effort=none` e
  `LLM_MAX_OUTPUT_TOKENS_RETRY` (default 1024). `reasoning_content` nunca e
  usado como resposta.
- [x] Defaults: `LLM_MAX_OUTPUT_TOKENS=512`, `LLM_TIMEOUT_SECONDS=120`.
- [x] `.env.example` e `.env.development.example` atualizados; `LLM_MODEL`
  comentado com o exemplo `qwen3.5-4b@q4_k_m`.
- [x] Alerta Prometheus `AImaginatorLlmUnavailable` inclui `truncated`.

### Bloco 2 - unload do LM Studio

- [x] `LmsCliUnloader` roda `lms unload --all` sem shell, timeout default 20 s.
- [x] `LLM_UNLOAD_AFTER_USE` (default true em development) e `LMS_CLI_PATH`.
- [x] Executado ao final do `assistant_llm`, antes de `_run_engine`; falha,
  timeout ou CLI ausente apenas logam e incrementam
  `aimaginator_llm_unload_total`.
- [x] Testes com executavel falso: sucesso, falha, timeout e ausente. A guarda
  `MIN_FREE_RAM_MB` continua no inicio do engine, depois do unload.
- [x] README documenta o fluxo.

### Bloco 3 - fila

- [x] `task_acks_late=True` e `task_reject_on_worker_lost=True`.
- [x] Falha de enqueue marca a Generation `FAILED` com `queue_publish_failed`,
  devolve credito/cota (idempotente), publica SSE e responde erro localizado.
- [x] Reconciliador `queue_lost` para `queued`/`processing` sem heartbeat por
  `QUEUE_STALE_SECONDS` (default 900), com relogio injetavel, refunds
  idempotentes e evento SSE.
- [x] Reconciliador roda no startup do worker e ao abrir stream/historico.
- [x] Heartbeat: PROCESSING e cada progresso fazem save+commit de `updated_at`
  em transacao curta (worker passa `commit=session.commit`).
- [x] Task reentregue com estado terminal sai sem trabalho.
- [x] Mensagens `queue_publish_failed`/`queue_lost` nos 11 locales e no
  catalogo do frontend.

### Bloco 4 - seguranca do ambiente de dev

- [x] Guarda `enforce_local_infra` na API e no worker: em development, hosts
  remotos em DB/Redis/RabbitMQ/Celery/S3 falham o boot sem imprimir
  credenciais, salvo `ALLOW_REMOTE_INFRA_IN_DEV=true`.
- [x] `.env.development` tem precedencia em development; `.env` de producao
  nao e carregado nesse modo. `ENV_FILE` explicito vence.
- [x] README mostra como conferir o broker efetivo sem segredos.

### Bloco 5 - logs sem conteudo do usuario

- [x] `content_preview`/`raw_preview` removidos por padrao.
- [x] `LLM_DEBUG_LOG_CONTENT=true` so libera preview em development, truncado
  e passado pelo scrubber; `ValidationError` nao vaza `input_value`.
- [x] Logs mantem tentativa/status/tempo/finish_reason/tokens/tamanhos/branch/
  tipo/mensagem, com ASCII-safe no console Windows.

### Bloco 6 - scripts e documentacao

- [x] `tools/smoke_assistant.py` imprime finish_reason, tokens de saida,
  truncamento, latencia da primeira/seguintes e avisa se
  `LLM_REASONING_EFFORT` estiver vazio. Nao executado.
- [x] README: escolha do modelo, unload, filas orfas e infra de dev.

### Bloco 7 - validacao

- [x] `pytest tests`: **435 coletados, 431 passed, 4 skipped**.
- [x] `pytest specs/evals`: **4 passed, 1 skipped** (sem LLM real).
- [x] `vitest`: **43 passed**.
- [x] Playwright: **14 passed**.
- [x] `tsc --noEmit`: limpo.
- [x] `npm run lint`: 0 erros (2 warnings pre-existentes em `auth-ui.tsx`).
- [x] `ruff check`: limpo nos arquivos alterados.
- [x] Nenhum modelo real, FLUX/Kontext ou script manual executado.
- [x] Nenhum commit/push.

## Fase 7.6 - categoria de bloqueio e qualidade da reescrita

### Bloco 1 - categoria decidida em codigo

- [x] Categoria final derivada dos booleanos de `moderation`; prioridade
  sexual > hate > gore > self_harm.
- [x] `blocked_category` do modelo nao vence booleanos; divergencias viram a
  metrica `aimaginator_llm_category_mismatch_total` (declarado/derivado, sem
  texto).
- [x] Sem booleanos, `blocked_category` so e aplicado com confianca
  `>= LLM_BLOCK_CONFIDENCE`; abaixo disso segue a politica de escopo
  existente (documentado no README).
- [x] Testes de categoria isolada, combinacoes sexual+self_harm e gore+hate,
  divergencia, fallback por confianca e mensagem localizada correta.

### Bloco 2 - system prompt e validacao da reescrita

- [x] Definicoes exclusivas por categoria, prioridade, exemplos abstratos e
  casos-limitrofes permitidos (anatomia educativa, cena historica).
- [x] Regras (a)-(f): fidelidade, sem enfeites de qualidade/resolucao, sem
  negacoes, preservar nomes/marcas, ~60 palavras, edicao com a frase padrao.
- [x] Validacao deterministica de `flux_prompt`/`kontext_instruction`:
  UMA tentativa de reparo; se persistir/invalido/indisponivel, sanitiza por
  substituicao e segue sem falhar o job.
- [x] "Keep everything else the same" permitido; nenhum texto de prompt ou
  reescrita em log.
- [x] Testes com LLM falso para cada termo proibido, cada negacao, reparo
  limpo, reparo persistente, reparo invalido e reparo indisponivel.

### Bloco 3 - smoke e evals

- [x] `tools/smoke_assistant.py` imprime booleanos de moderation, categoria
  final, divergencia e `obtido=injection` nos casos de injecao. Nao executado.
- [x] `specs/evals`: 33 casos de regressao (11 locales x 3 grupos):
  sexual-nao-self_harm, self_harm-nao-sexual e pedido-vago-sem-enfeites.
  Eval real marcada e ignorada sem `RUN_LLM_EVALS=1`; teste de dados roda
  sem LLM.

### Bloco 4 - validacao

- [x] `pytest tests`: **457 coletados, 453 passed, 4 skipped**.
- [x] `pytest specs/evals`: **7 coletados, 5 passed, 2 skipped** (sem LLM real).
- [x] `ruff check .`: limpo.
- [x] `npm run lint`: 0 erros (2 warnings pre-existentes em `auth-ui.tsx`).
- [x] `tsc --noEmit`: limpo.
- [x] Nenhum LLM/FLUX/Kontext ou `tools/smoke_*.py` executado.
- [x] Branch atual `main`: regra de commit/push nao se aplica; nada commitado.

## Fase 8 - seguranca, E2E, limpeza, documentacao e entrega

### Bloco 1 - revisao de seguranca

- [x] IDOR/dono/sessao anonima cobertos por testes A/B; `original_object_key`
  nunca aparece em API/SSE/galeria/historico.
- [x] SSE usa ticket efemero single-use no Redis (TTL 60s); JWT nao vai na URL.
- [x] `sd-cli` recebe argv em lista, sem shell; prompt sanitizado (controle,
  quebras, limite 2000, prefixo para `-`); testes com `--help`, aspas, unicode
  e string longa.
- [x] Upload: pixels/assinatura real, reencode PNG sem metadados, temp dir
  aleatorio e sem path traversal; SSRF via `SecureImageFetcher`.
- [x] `S3_PRESIGN_EXPIRES_SECONDS` configuravel; URLs assinadas nao vao para log.
- [x] TokenBucket usa `redis.call('TIME')`; teste com relogio local divergente.
- [x] CORS/CSP/headers revisados; rate limit por rota sensivel.
- [x] `pip-audit`: 279/30 -> 44/7 apos remover `crewai`/`langchain` diretos e
  164 pacotes; restantes em `starlette`, cadeia `langgraph` (lazy) e `pytest`
  (dev). `npm audit --omit=dev`: 0; completo: 8 moderadas de dev.
- [x] `docs/agent/SECURITY_REVIEW.md` atualizado.

### Bloco 2 - feature flag e producao

- [x] `FEATURE_IMAGE_GENERATION_ENABLED` (false em producao, true em dev),
  `feature_disabled` 503 localizado nos 11 locales e `/api/v1/config` para o
  frontend (aviso "em breve" e envio desabilitado).
- [x] Validacao de sdcpp/S3/LLM condicional a flag + `IMAGE_ENGINE=sdcpp`.
- [x] Migrations aditivas/idempotentes com downgrade; geracoes antigas sem
  original retornam `original_unavailable` em refino/upscale (backfill
  documentado, sem erro 500).

### Bloco 3 - E2E com infra local

- [x] `tests/integration/test_e2e_infra.py` cobre geracao, edicao por upload,
  refino, variacao, upscale Lanczos, SSE, URL assinada, marca d'agua e
  metadados; caminhos opcionais de moderacao de texto/imagem e limite.
- [x] Pulado por padrao (`RUN_E2E_INFRA=1`); README e MANUAL_VALIDATION
  documentam como rodar.

### Bloco 4 - CI

- [x] `.github/workflows/ci.yml` executa ruff, pytest tests/specs/evals,
  lint/tsc/vitest/build do frontend, Playwright mockado, paridade via vitest e
  auditorias informativas, sem segredos.
- [x] `lupa` passou para o grupo dev; CI nao instala mais manualmente.

### Bloco 5 - limpeza e consistencia

- [x] `crewai`/`langchain` diretos removidos (nao usados); `langgraph`
  permanece lazy/opcional com fallback sequencial; `IMAGE_ENGINE=stub` intacto.
- [x] `.gitignore` revisado (envs, modelos, saidas, imagens de teste, logs,
  caches).
- [x] README, PROGRESS, FINAL_REPORT, MANUAL_VALIDATION e ADRs atualizados.
- [x] Politica de categoria/reescrita documentada; licencas FLUX/Kontext e
  modelos de moderacao registradas; backfill documentado.

### Bloco 6 - varredura de segredos e arquivos grandes

- [x] Nenhum `.env` real rastreado ou no historico; apenas `*.example`.
- [x] Nenhuma chave `sk-`, `AIza`, `AKIA`, `Bearer`, chave privada ou DSN com
  credenciais; unico `SECRET_KEY` e placeholder de exemplo.
- [x] Nenhum blob versionado > 5 MB; nenhum modelo/peso ou imagem de teste
  nova. Logo do backend e o unico asset de imagem novo.

### Bloco 7 - testes finais

- [x] `pytest tests`: **457 coletados, 453 passed, 4 skipped**.
- [x] `pytest specs/evals`: **7 coletados, 5 passed, 2 skipped** (sem LLM real).
- [x] Vitest: **43 passed** (11 arquivos).
- [x] Playwright: **14 passed**.
- [x] `npm run lint`: 0 erros (2 warnings preexistentes em `auth-ui.tsx`).
- [x] `npx tsc --noEmit`: limpo.
- [x] `npm run build`: sucesso (Next.js 16.4.5).
- [x] `ruff check .`: limpo.

### Bloco 8 - validacao manual

- [x] `docs/agent/MANUAL_VALIDATION.md` com a ordem dos smoke tests, cuidados
  termicos, `LLM_REASONING_EFFORT`, unload, limiares e flags do E2E.

### Bloco 9 - entrega

- [ ] Branch `feat/local-flux-engine`, commits organizados e push.
  (Executado ao final; a `main` nao recebe commits.)

## Fase 9 - plataforma e operacao

### Dependencias
- [x] FastAPI 0.162, Starlette 1.10, LangGraph 1.2; `pip-audit` 279/30 -> 3/2
  (langsmith e pytest em excecoes datadas). npm producao 0; dev 8 moderadas.
- [x] `crewai`/`langchain` removidos; fallback sequencial mantido.

### Disponibilidade, worker remoto e motor hospedado
- [x] Heartbeat de worker com id/capacidades/engine/estado/last_seen/TTL e
  thread no processo principal; estados idle/busy/cooling testados com relogio
  falso.
- [x] `EngineAvailabilityService`, `/api/v1/status`, 503 `engine_offline` e
  `maintenance` sem consumir credito/cota; mensagens nos 11 locales.
- [x] `WORKER_MODE=remote` com exigencia de TLS no dev_guard e
  `docs/deploy/REMOTE_WORKER.md` (SQL/IAM/broker de menor privilegio).
- [x] `HttpHostedEngine` (POST + polling) e fallback ordenado, testado com
  transporte HTTP falso.

### Guarda termica
- [x] `HardwareSensorPort`, LibreHardwareMonitor/none, settings, aborto por
  temperatura/RAM, cooling e metricas; teste com sensor falso.
- [x] `tools/hw_exporter.py` criado (comando manual, nao executado).

### Creditos, planos e uso
- [x] Migration `credit_ledger`, `users.plan/role/credits_period_start/
  avatar_object_key`; saldo materializado com `FOR UPDATE`.
- [x] Reset mensal idempotente no acesso e startup; ledger para consume/refund/
  admin_adjust.
- [x] `GET /api/v1/users/me/usage` e painel de uso no frontend.

### Admin
- [x] `require_admin`, rotas de sinalizados, stats, block/unblock, creditos,
  workers, manutencao, auditoria e fila de denuncias placeholder.
- [x] `admin_audit_log`; respostas sem prompt/email; UI `/[locale]/admin`.

### i18n
- [x] GLOSSARY, REVIEW_CHECKLIST, `_review.json` e teste de paridade.
- [x] Pseudo-localizacao opt-in e teste de overflow 360 px nos 11 idiomas.

### C2PA e legado
- [x] Grupo opcional `provenance`; `C2PA_REQUIRED` fail-closed; tools de
  certificado DEV e verificacao.
- [x] Backfill `--dry-run`/`--apply` idempotente; avatar no S3 via proxy.

### CI/CD e supply chain
- [x] Dependabot, CodeQL, gitleaks, gates pip/npm, build Docker com Trivy
  informativo, compose prod-like, Alertmanager opcional e CHANGELOG.

### Testes finais
- [x] `pytest tests`: **489 coletados, 485 passed, 4 skipped**.
- [x] `specs/evals`: **7 coletados, 5 passed, 2 skipped** (sem LLM real).
- [x] Vitest: **45 passed**; Playwright: **36 passed**.
- [x] `tsc`: limpo; lint 0 erros (2 warnings preexistentes); `next build` ok.
- [x] `ruff check .`: limpo.
- [x] Nenhum modelo real/FLUX/smoke executado.

## Entrega

Branch: `feat/local-flux-engine`. Commits organizados e push conforme Bloco 9.
Nenhum modelo real, script manual ou eval real foi executado.

## Pendências para o usuário

- Rodar smoke tests/evals reais e calibrar limiares.
- Revisar traduções com nativos.
- Emitir certificado C2PA confiável se desejado.
- Definir host/modelo de produção e ligar a feature flag.
- Backfill de `original_object_key` para gerações antigas.
- Provisionar Prometheus/Grafana/Alertmanager e exporter de VRAM/temperatura.
