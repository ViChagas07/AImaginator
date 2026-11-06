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
