# AImaginator — Relatório final

## O que existe

- FastAPI assíncrona com Clean Architecture modular, JWT/OAuth Google,
  rate limiting, cota diária, penalidades e erros localizados.
- Worker Celery com concorrência 1, reciclagem por task, timeouts por kind,
  DLQ, progresso real e correlação por geração.
- Motor local FLUX.1 Dev/Kontext via stable-diffusion.cpp atrás de portas;
  `IMAGE_ENGINE=stub` permanece para testes.
- Assistente de prompts multilíngue (LM Studio/OpenAI-compatible) no worker,
  com fail-closed, moderação e reescrita para FLUX/Kontext.
- Pipeline de saída: moderação visual, original privado, marca d'água
  obrigatória, metadados de IA e versão pública assinada.
- Upscale 2× Lanczos/ESRGAN com limite diário próprio.
- Frontend Next.js em 11 locales, RTL, estúdio (proporção/seed/variação/
  refino/upload/histórico/upscale), SSE e estados localizados.
- Storage S3/MinIO, migrations Alembic, Sentry, Prometheus/Grafana, CI sem
  segredos, scripts manuais e ADRs.

## Como validar

- Automático: `poetry run pytest tests`, `poetry run pytest specs/evals -m eval`,
  `npm run test`, `npm run test:e2e`, `npm run lint`, `npx tsc --noEmit`,
  `npm run build`, `ruff check .`.
- Manual com modelos reais: ver `docs/agent/MANUAL_VALIDATION.md`.
- E2E com infraestrutura: `tests/integration/test_e2e_infra.py` com
  `RUN_E2E_INFRA=1`.

## Pendências conhecidas

- Rodar os smoke tests e evals reais; calibrar limiares.
- Revisar traduções com falantes nativos.
- Emitir certificado C2PA confiável se a assinatura for desejada.
- Definir host/modelo de produção; hoje a flag mantém a geração desligada.
- Backfill de `original_object_key` para gerações antigas.
- Exporter de VRAM/temperatura (HWiNFO/Adrenalin hoje).

## Atualizacoes finais (Fases 7.5/7.6)

- Cliente LLM com `reasoning_effort=none`, retry unico de truncamento e
  `reasoning_content` fora do contrato publico.
- Modelo recomendado para 8 GB de VRAM: `qwen3.5-4b@q4_k_m`; o 9B continua
  suportado, mas e mais lento e pressiona RAM.
- Descarregamento opcional do LM Studio via `lms unload --all` antes do FLUX.
- Fila com ack tardio, `queue_publish_failed`, reconciliacao `queue_lost` e
  heartbeat de `updated_at`.
- Guarda de infraestrutura local em development; `.env.development` tem
  precedencia.
- Categoria de bloqueio derivada dos booleanos (sexual > hate > gore >
  self_harm) e reescrita sem enfeites/negacoes, com reparo deterministico.
- Logs sem conteudo de prompt/reescrita por padrao.

## Resultado da Fase 8

- Backend: `457` testes coletados, `453 passed`, `4 skipped`; evals `7`
  coletados, `5 passed`, `2 skipped` (sem LLM real).
- Frontend: `43` testes vitest, `14` Playwright, lint sem erros, `tsc` limpo e
  `next build` concluido.
- CI movido/validado em `.github/workflows/ci.yml`; roda sem segredos e sem o
  grupo opcional de moderacao.
- E2E de infraestrutura em `tests/integration/test_e2e_infra.py`, pulado por
  padrao (`RUN_E2E_INFRA=1`), com caminhos opcionais de moderacao.
- Revisao de seguranca em `docs/agent/SECURITY_REVIEW.md`: ticket SSE,
  IDOR, argv sanitizado, upload, SSRF, presign, TokenBucket, CORS/CSP e
  auditoria de dependencias (44 vulnerabilidades conhecidas restantes em 7
  pacotes; npm producao 0).
- Varredura de segredos: nenhum `.env` real/modelo/imagem de teste/arquivo
  >5 MB; apenas placeholders de exemplo.
- `crewai`/`langchain` diretos removidos; `langgraph` permanece lazy/opcional.

### Pendencias antes de producao

- Rodar os smoke tests e evals reais e calibrar limiares.
- Revisar traducoes com falantes nativos.
- Emitir certificado C2PA confiavel se desejado.
- Definir host/modelo de producao e manter `FEATURE_IMAGE_GENERATION_ENABLED`
  desligada ate a validacao.
- Planejar upgrade major de `starlette`/FastAPI e da cadeia `langgraph` para
  eliminar as CVEs restantes.


## Fase 9 - plataforma

- Dependencias: FastAPI 0.162, Starlette 1.10, LangGraph 1.2; auditoria em
  3 vulnerabilidades conhecidas (langsmith/pytest) cobertas por excecoes
  datadas; npm producao 0.
- Novo: heartbeat de workers, `/api/v1/status`, `WORKER_MODE=remote`,
  `HttpHostedEngine` com fallback, guarda termica/RAM, ledger de creditos com
  planos e reset mensal, console admin auditado, avatar no S3, backfill,
  pseudo-localizacao, C2PA opcional `provenance`, Dependabot/CodeQL/gitleaks
  e gates de auditoria.
- Testes finais: backend 489 coletados/485 passed/4 skipped; evals 7/5/2;
  vitest 45; Playwright 36; lint/tsc/build/ruff verdes.
- Pendencias: calibracao termica e de limiares com hardware real, revisao
  nativa das traducoes (review status `pending`), certificado C2PA de CA
  confiavel, deploy real do worker remoto e testes E2E com infraestrutura.


## Fase 10 - produto (parcial)

Entregue no backend: colecoes/favoritos/tags, busca full-text, soft delete em
lote, export ZIP, links publicos com token hasheado, denuncias com fila admin,
presets deterministicos, cancelamento com CANCELED/refunds e retry de geracao.
No frontend: chips de estilo, cancelamento, pagina publica de compartilhamento
com denuncia e metadata OpenGraph.

Lacunas declaradas: UI completa de biblioteca (selecao/filtros/colecoes),
retry para edicao/upscale, notificacoes do navegador e proporcao sugerida.
Testes: backend 499/495/4; evals 7/5/2; vitest 45; Playwright 37.
