# AImaginator

> API + aplicação web para **gerar e editar imagens com IA** a partir de
> instruções em linguagem natural.

O AImaginator é um produto full-stack profissional: seguro, observável,
testado (TDD + EDD), responsivo, acessível (POUR) e otimizado para
descoberta (SEO/AEO/GEO). O usuário descreve o que quer, envia uma imagem
existente para edição, acompanha o progresso em tempo real (SSE) e mantém um
histórico de gerações.

---

## Índice

1. [Visão geral](#visão-geral)
2. [Stack tecnológica](#stack-tecnológica)
3. [Arquitetura](#arquitetura)
4. [Como rodar localmente](#como-rodar-localmente)
5. [Testes e Evals](#testes-e-evals)
6. [Variáveis de ambiente](#variáveis-de-ambiente)
7. [Segurança](#segurança)
8. [Deploy](#deploy)
9. [CI/CD](#cicd)
10. [Decisões arquiteturais (ADRs)](#decisões-arquiteturais-adrs)

---

## Visão geral

- **Gerar**: `POST /api/v1/generations` com um prompt textual.
- **Editar**: `POST /api/v1/generations/edits` com a URL de uma imagem + prompt.
- **Acompanhar**: `GET /api/v1/generations/{id}/stream` (Server-Sent Events).
- **Histórico**: listagem paginada por cursor + galeria pública curada.
- **Variação**: `POST /api/v1/generations/{id}/variations` cria nova geração
  com o mesmo prompt/proporção e uma seed nova (conta na cota diária).
- **Refinar (edição encadeada)**: `POST /api/v1/generations/edits` aceita
  `source_generation_id` além de upload/URL e grava `parent_generation_id`.
- **Seed/proporção**: `aspect_ratio` (1:1, 4:3, 3:4, 16:9, 9:16) e `seed`
  opcional (0 a 4294967295) no request; a seed usada volta no resultado e no
  histórico. Upload de edição aceita PNG/JPEG até 10 MB e 8192 px por lado.
- **Upscale**: `POST /api/v1/generations/{id}/upscale` amplia 2x o original
  privado com limite diário próprio.
- **SSO**: login com Google (OAuth 2.0 + OpenID Connect, Authorization Code + PKCE).

A geração de imagem **nunca** é processada de forma síncrona no request HTTP:
ela é enfileirada no Celery (RabbitMQ) e o cliente acompanha o progresso via
SSE.

## Stack tecnológica

| Camada                     | Tecnologia                                                        |
| -------------------------- | ----------------------------------------------------------------- |
| Frontend                   | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Zustand |
| i18n / a11y                | next-intl (11 locales completos), hreflang, POUR          |
| Backend                    | FastAPI (Python 3.11, assíncrono)                                 |
| Banco de dados             | PostgreSQL                                                         |
| ORM                        | SQLAlchemy 2.x assíncrono + Pydantic v2 + Alembic                  |
| Cache                      | Redis (Stale-While-Revalidate)                                    |
| Mensageria                 | RabbitMQ + Celery                                                  |
| Agentes de IA              | LangGraph opcional (lazy) + fallback sequencial (atrás de uma porta)                |
| Auth                       | OAuth 2.0 + OpenID Connect via Authlib (Google), PKCE, JWT         |
| Tempo real                 | SSE (Redis Pub/Sub como bridge)                                   |
| Observabilidade            | Prometheus + Grafana + Sentry + structlog                         |
| Empacotamento Python       | Poetry (Python 3.11)                                              |
| Deploy                     | Vercel (frontend) / Docker (backend, workers)                     |
| CI/CD                      | GitHub Actions + Docker Compose                                   |
| Context Engineering        | GraphiFy (spec-driven development)                                |

## Arquitetura

**Monolito Modular + Clean Architecture por módulo.** Um único deployable,
particionado em módulos de domínio fracamente acoplados; dentro de cada
módulo, quatro camadas com dependência apontando para dentro:

```
aimaginator/
├── apps/
│   ├── api/                    # FastAPI — composição, routers, middlewares, DI
│   └── web/                    # Next.js (App Router, i18n, SEO/AEO/GEO)
├── modules/
│   ├── image_generation/       # domain/ application/ adapters/ infra/
│   ├── auth/                   # OAuth2/OIDC + PKCE + JWT
│   ├── rate_limiting/          # Token Bucket + Circuit Breaker + Bulkhead
│   ├── users/                  # entidade + repositório
│   └── observability/          # Prometheus + Sentry + structlog
├── workers/
│   └── celery_app/             # tasks assíncronas de geração (filas + DLQ)
├── shared_kernel/              # erros/tipos realmente comuns (mínimo)
├── specs/                      # SDD — uma spec por caso de uso + evals EDD
├── context_graph/              # artefatos GraphiFy (Context Engineering)
├── infra/
│   ├── settings.py             # ÚNICO ponto de leitura de variáveis de ambiente
│   ├── database.py / redis_client.py
│   ├── docker/                 # docker-compose, Dockerfiles, prometheus, grafana
│   └── github/workflows/       # CI/CD
├── alembic/                    # migrations (modo assíncrono)
├── pyproject.toml              # Poetry, Python 3.11
├── .env.example                # template de variáveis (NUNCA valores reais)
└── README.md
```

**Regra de acoplamento**: cada módulo expõe apenas um contrato público
(`contracts.py`). Nenhum módulo importa diretamente de `domain/` ou
`adapters/` de outro módulo.

### Fluxo de uma geração

```
Client ──POST /generations──▶ FastAPI ──valida prompt (anti-injection) + quota──▶ PostgreSQL
                                      │
                                      └──enfileira──▶ RabbitMQ ──▶ Celery worker
                                                                        │
                                      ┌─────────────────────────────────┘
                                      │ Pipeline: interpret → safety → generate/edit → post
                                      │   (LangGraph opcional; fallback sequencial, atrás de porta)
                                      ▼
                              Redis Pub/Sub ──▶ FastAPI (SSE bridge) ──▶ Client (EventSource)
```

## Como rodar localmente

### Pré-requisitos

- Docker + Docker Compose (a forma mais simples — sobe a infraestrutura).
- Ou: Python 3.11 + Poetry + Node 22 (para desenvolvimento).
- **Não use o `.env` da raiz em desenvolvimento:** ele está em modo
  `production`. Use `.env.development`, copiado de `.env.development.example`.

### 1. Subir a infraestrutura (Docker Compose)

```bash
cp .env.development.example .env.development   # ajuste se necessario
docker compose --env-file .env.development -f infra/docker/docker-compose.yml up --build
```

Isso sobe: `api` (host 8001 → container 8000), `worker` (Celery com
`concurrency=1`), `postgres` (host **5433**), `redis` (host **6380**),
`rabbitmq` (host **5673/15673**), `minio` (host **9002/9003**),
`prometheus` (host **9091**) e `grafana` (host **3002**). As portas
alternativas evitam conflito com a stack do ForjaB2B. O MinIO é o storage S3
do modo `IMAGE_ENGINE=sdcpp` (bucket criado automaticamente em desenvolvimento).

### 2. Backend (sem Docker, para desenvolvimento)

```powershell
Copy-Item .env.development.example .env.development
$env:ENV_FILE = ".env.development"   # faz o Settings ler o arquivo de dev
poetry install --with dev
poetry run alembic upgrade head
poetry run uvicorn apps.api.main:app --reload --port 8001
```

Em outro terminal, repita `$env:ENV_FILE = ".env.development"` e suba o worker:

```powershell
$env:ENV_FILE = ".env.development"
poetry run celery -A workers.celery_app.celery:celery_app worker `
  --loglevel=info --queues=generation.standard `
  --concurrency=1 --max-tasks-per-child=1
```

> O worker não deve rodar com concorrência > 1: uma única difusão já
> consome praticamente toda a VRAM/RAM disponível.

### 3. Frontend (Next.js)

O frontend roda separadamente (Vercel é serverless; ver Deploy):

```bash
cd apps/web
npm install
# apps/web/.env.local:
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
npm run dev            # http://localhost:3000
```

> O `apps/web/.env.local` atual aponta para o Render (produção). Para
> desenvolvimento, aponte para a API local em `http://localhost:8001`.

## Assistente de prompts, moderação e penalidades

Com `IMAGE_ENGINE=sdcpp`, cada job chama primeiro o assistente local
(OpenAI-compatible, LM Studio) e só depois o FLUX/Kontext. O assistente entende
11 idiomas, corrige erros, classifica/modera o pedido e reescreve o prompt
(`flux_prompt` para geração, `kontext_instruction` para edição). O prompt
original continua salvo na `Generation`; o produto só devolve imagem ou recusa
padronizada.

Variáveis principais:

| Variável | Padrão | Função |
|---|---|---|
| `PROMPT_MAX_CHARS` | `1000` | limite do prompt na borda |
| `LLM_BASE_URL` | `http://localhost:1235/v1` | LM Studio |
| `LLM_MODEL` | `qwen/qwen3.5-9b` | modelo local |
| `LLM_API_KEY` | `lm-studio` | chave não vazia exigida pelo cliente |
| `LLM_TIMEOUT_SECONDS` | `120` | primeira chamada carrega o modelo |
| `LLM_MAX_OUTPUT_TOKENS` | `512` | tamanho do JSON |
| `LLM_MAX_OUTPUT_TOKENS_RETRY` | `1024` | retentativa unica se vier `finish_reason=length` sem `content` |
| `LLM_REASONING_EFFORT` | `none` | desliga o reasoning no LM Studio; vazio = nao envia o campo |
| `LLM_UNLOAD_AFTER_USE` | `true` em dev | executa `lms unload --all` antes do FLUX |
| `LMS_CLI_PATH` | vazio (`lms` do PATH) | caminho do executavel do LM Studio |
| `LLM_UNLOAD_TIMEOUT_SECONDS` | `20` | timeout do `lms unload` |
| `LLM_DEBUG_LOG_CONTENT` | `false` | loga preview de conteudo SO em development |
| `LLM_TTL_SECONDS` | `60` | descarrega o modelo após o uso quando aceito |
| `LLM_BLOCK_CONFIDENCE` | `0.5` | confiança mínima para bloqueio |
| `MOD_WARN_AT` / `MOD_BLOCK_AT` / `MOD_REVIEW_AT` | `3` / `5` / `10` | níveis na janela de 24h |
| `MOD_BLOCK_MINUTES` / `MOD_REVIEW_BLOCK_HOURS` | `60` / `24` | bloqueios |
| `MODERATION_STORE_PROMPT_TEXT` | `false` | não guarda texto; se true, trunca em 200 |

### Escolha do modelo do assistente

Para maquinas com **4 GB de VRAM** (ex.: Radeon RX 6500 XT), use
`qwen3.5-4b@q4_k_m`. O `qwen/qwen3.5-9b` Q4_K_M ocupa ~5,3 GB e transborda
para a memoria compartilhada, derrubando a geracao para ~3-10 tok/s e
pressionando a RAM do sistema. O 4B Q4_K_M cabe melhor na VRAM, responde mais
rapido e deixa RAM livre para o FLUX/Kontext.

Para trocar, no `.env.development`:

```dotenv
LLM_MODEL=qwen3.5-4b@q4_k_m
LLM_REASONING_EFFORT=none
LLM_MAX_OUTPUT_TOKENS=512
LLM_TIMEOUT_SECONDS=120
```

Se o modelo nao estiver carregado no LM Studio, a primeira chamada inclui o
carregamento e pode levar dezenas de segundos. `LLM_REASONING_EFFORT=none`
e obrigatorio para Qwen3.x no LM Studio: `chat_template_kwargs.enable_thinking`
nao e propagado pela API OpenAI-compatible.

### Descarregar o LLM antes do FLUX

`LLM_UNLOAD_AFTER_USE=true` (padrao em development) executa
`lms unload --all` em subprocesso **sem shell**, com timeout de 20 s, ao final
da etapa `assistant_llm` e antes do motor de imagem. Se `LMS_CLI_PATH` estiver
vazio, o worker tenta `lms` do PATH. Falha, timeout ou CLI ausente apenas
geram `llm_unload_failed` e a metrica `aimaginator_llm_unload_total`; o job
continua. A guarda `MIN_FREE_RAM_MB` do sd-cli e avaliada no inicio de
`_run_engine`, portanto **depois** do descarregamento.

### Filas orfas e infraestrutura de dev

O worker usa `task_acks_late=True` e `task_reject_on_worker_lost=True`; uma
task reentregue com a Generation ja terminal sai sem trabalho. Se o publish
no broker falhar, a geracao vira `queue_publish_failed` e o credito/cota sao
devolvidos. Geracoes `queued` (ou `processing` sem heartbeat) por mais de
`QUEUE_STALE_SECONDS` viram `queue_lost`; o reconciliador roda no startup do
worker e ao abrir o stream/historico.

Em `APP_ENV=development`, a API e o worker falham no boot se
`DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND` ou `S3_ENDPOINT_URL` apontarem para um host remoto.
Use `ALLOW_REMOTE_INFRA_IN_DEV=true` apenas conscientemente. O arquivo
`.env.development` tem precedencia em development (e o `.env` de producao nao
e carregado nesse modo). Para conferir o broker efetivo sem imprimir
credenciais:

```powershell
poetry run python -c "from urllib.parse import urlsplit; from infra.settings import get_settings; s=get_settings(); print('broker=', urlsplit(s.celery_broker_url).hostname, urlsplit(s.celery_broker_url).port); print('redis=', urlsplit(s.redis_url).hostname, urlsplit(s.redis_url).port)"
```

### Politica de moderacao do assistente

A categoria final e decidida em codigo a partir dos booleanos
`moderation.sexual`, `moderation.gore`, `moderation.hate` e
`moderation.self_harm`; o campo `blocked_category` do modelo nao decide
sozinho. Quando mais de um booleano e true, a prioridade e:
**sexual > hate > gore > self_harm**. Se o campo declarado divergir dos
booleanos, os booleanos vencem e a divergencia e registrada apenas na metrica
`aimaginator_llm_category_mismatch_total` (rotulos declarado/derivado, sem
texto do prompt).

Se nenhum booleano for true e `blocked_category` vier preenchida, o campo e
tratado como inconsistencia: ele so bloqueia quando a confianca for
`>= LLM_BLOCK_CONFIDENCE`. Abaixo disso a decisao segue a politica existente
de escopo (pedido dentro de escopo e permitido; fora de escopo recebe a
recusa localizada), sem confiar no campo isolado.

### Regras de reescrita do assistente

`flux_prompt` e `kontext_instruction` devem ser fieis ao pedido e ao estilo
solicitado. Nao podem acrescentar enfeites de qualidade/resolucao ("8k",
"4k", "ultra detailed", "hyper-realistic", "masterpiece", "highly detailed")
nem estilo/iluminacao nao pedidos (no maximo uma frase curta neutra quando o
pedido for muito vago). Devem descrever apenas o que deve aparecer, sem
negacoes em ingles ("without", "no", "avoid", "not", "free of"), preservar
nomes de personagens/marcas exatamente e ficar em ~60 palavras. Para edicao,
a instrucao padrao e "Change only X to Y. Keep everything else the same.".

Se a saida contiver termos proibidos, o assistente faz UMA tentativa de
reparo. Se o reparo persistir, invalido ou indisponivel, a lista e removida
por substituicao deterministica e o job continua. As metricas
`aimaginator_llm_rewrite_repairs_total` registram o desfecho sem texto.

Relação entre as duas cotas: `generation_credits` é o saldo de gerações da
conta; a cota diária é uma janela deslizante de 24 horas por prompt. Ambas são
verificadas na requisição. Recusas do LLM, recusas de moderação e falhas do
motor devolvem a chance diária e o crédito de geração de forma idempotente
(`generations.quota_refunded` / `credits_refunded`). A penalidade de moderação
continua valendo, então devolver o crédito não abre espaço para abuso.

O locale do site vai no header `X-Locale` (fallback `Accept-Language`,
`pt-BR`). Recusas e avisos são localizados nos 11 locales suportados.
Injeção/escopo não geram penalidade; moderação gera aviso (3), bloqueio de 1h
(5) e revisão + bloqueio de 24h (10). Recusa do LLM e falha do motor devolvem
a chance diária.

Evals reais do assistente (não rodam em CI; exigem o modelo carregado):

```bash
RUN_LLM_EVALS=1 pytest specs/evals -m eval -k prompt_assistant -s
```

## Estúdio (interface)

O estúdio (`/[locale]/studio`) oferece:

- alternância entre **Gerar** e **Editar imagem** (edição exige login);
- seletor de proporção (1:1, 4:3, 3:4, 16:9, 9:16) e seed avançada opcional;
- upload PNG/JPEG por drag-and-drop ou seletor, com preview e validação
  client-side dos mesmos limites do backend;
- progresso real por SSE, estimativa de tempo traduzida e recusas/avisos
  localizados enviados pelo backend;
- ações **Baixar**, **Gerar variação** e **Refinar** (edição encadeada);
- histórico paginado com miniaturas, prompt, data, ações e cadeia de
  refinamentos (`parent_generation_id`).

A interface está nos 11 locales (pt-BR, en, es, fr, de, it, ja, zh, ko, ru, ar),
com layout RTL em árabe, propriedades lógicas (`ms-/me-/ps-/pe-`,
`text-start/end`) e fontes Noto para CJK/árabe.

## Saída protegida: moderação, marca d'água, metadados e upscale

Toda imagem gerada/editada passa por: validação -> moderação da imagem ->
`generations/{id}/original.png` (privado) -> marca d'água -> metadados de IA
-> `generations/{id}/result.png` (público). Apenas a versão pública é servida
por URL assinada; a chave do original nunca aparece em respostas. Refino e
upscale leem o original limpo.

**Moderação de imagem.** `IMAGE_MODERATION_ENABLED=true` e
`IMAGE_MODERATOR=fake` são o padrão de desenvolvimento. Para produção, copie
os pesos (NSFW Falconsai e CLIP) para caminhos locais, instale o grupo
opcional e configure:

```bash
poetry install --with moderation
# baixe os pesos manualmente (ex.: huggingface-cli) e aponte os caminhos:
huggingface-cli download Falconsai/nsfw_image_detection --local-dir models/nsfw
huggingface-cli download openai/clip-vit-base-patch32 --local-dir models/clip
# IMAGE_MODERATOR=local
# IMAGE_NSFW_MODEL_PATH=./models/nsfw
# IMAGE_CLIP_MODEL_PATH=./models/clip
```

`IMAGE_NSFW_THRESHOLD`, `IMAGE_GORE_THRESHOLD`, `IMAGE_HATE_THRESHOLD` e
`IMAGE_SELF_HARM_THRESHOLD` controlam os limites. Nas imagens Docker, inclua
`--with moderation` no comando de `poetry install` do worker para embarcar o
grupo opcional. Se o moderador real falhar,
a imagem não é publicada (`image_moderation_unavailable`, fail-closed).
Origem de edição bloqueada apaga o S3 e conta penalidade; imagem gerada
bloqueada não conta penalidade, mas devolve crédito/cota.

**Marca d'água.** Sempre aplicada, sem opção de pular. O asset
`modules/image_generation/assets/AImaginator_pic_transparent.png` é validado no
startup. Ajuste por `WATERMARK_LOGO_PATH`, `WATERMARK_WIDTH_RATIO`,
`WATERMARK_MIN_WIDTH_PX`, `WATERMARK_MARGIN_RATIO`, `WATERMARK_OPACITY` e
`WATERMARK_SHADOW`.

**Metadados de IA.** Todas as imagens públicas recebem PNG tEXt/iTXt + XMP/IPTC
com `DigitalSourceType=trainedAlgorithmicMedia`, gerador AImaginator, modelo
(FLUX.1 Dev/Kontext) e data UTC. Nunca prompt, seed, usuário ou e-mail. C2PA é
opcional (`C2PA_ENABLED=false` por padrão); em produção use certificado/chave
emitidos por uma CA confiável (`C2PA_CERT_PATH`, `C2PA_KEY_PATH`). A ausência
da lib/certificado gera aviso e não bloqueia a imagem.

**Upscale.** `POST /api/v1/generations/{id}/upscale` (login + dono + DONE)
cria `kind=upscale`, lê o original privado, amplia 2x e aplica marca/metadados.
Não usa o assistente, não repete moderação e não consome cota de prompts.
Limite próprio `UPSCALE_DAILY_LIMIT` (5/24h). `UPSCALE_ENGINE=lanczos` usa
Pillow; `esrgan` usa o sd-cli com `SDCPP_UPSCALE_MODEL_PATH` e
`UPSCALE_TIMEOUT_SECONDS`. A suíte roda sem o grupo `moderation`.

### Backfill de originais

Geracoes antigas podem nao ter `original_object_key` (antes da Fase 6). Refinar
ou ampliar essas geracoes retorna `original_unavailable` (409) com mensagem
localizada, sem erro 500; nao ha backfill automatico. O campo
`original_object_key` nunca aparece em API, SSE, historico ou galeria.

## Modo FLUX/Kontext local (`IMAGE_ENGINE=sdcpp`)

O runtime real e o `sd-cli` do stable-diffusion.cpp. **Nenhum teste automatizado
executa o modelo**: a suite usa um executavel falso (`tests/fakes/fake_sd_cli.py`).

1. Copie `.env.development.example` para `.env.development` e preencha os
   caminhos absolutos de `SDCPP_BINARY_PATH`, `SDCPP_VAE_PATH`,
   `SDCPP_CLIP_L_PATH`, `SDCPP_T5XXL_PATH`, `SDCPP_GEN_MODEL_PATH` e
   `SDCPP_EDIT_MODEL_PATH`.
2. Defina `IMAGE_ENGINE=sdcpp` e o storage (`S3_ENDPOINT_URL`, `S3_BUCKET`,
   `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`). Em desenvolvimento o bucket
   e criado automaticamente; as imagens sao servidas por URL assinada.
3. Suba a infraestrutura (Postgres 5433, Redis 6380, RabbitMQ 5673/15673,
   MinIO 9002/9003):

   ```bash
   docker compose --env-file .env.development -f infra/docker/docker-compose.yml up -d postgres redis rabbitmq minio
   ```

4. Suba a API e o worker com o mesmo `.env.development` (o worker deve rodar
   com `--concurrency=1 --max-tasks-per-child=1`).
5. Smoke test manual (o usuario roda; nao e executado pelo agente):

   ```bash
   python tools/smoke_sdcpp.py                 # geracao 512x512, 8 steps
   python tools/smoke_sdcpp.py --edit --source entrada.png
   ```

   O script imprime RAM livre antes/depois, tempo por etapa e recomenda
   monitorar temperatura/energia. O PC de desenvolvimento ja desligou sob
   carga longa do Kontext.

Variaveis novas: `MIN_FREE_RAM_MB` (padrao 6000; aborta sem iniciar o processo),
`COOLDOWN_SECONDS_BETWEEN_JOBS` (padrao 0; pausa protege o hardware),
`S3_PRESIGN_EXPIRES_SECONDS` e `S3_SOURCE_RETENTION_HOURS`. As origens de
edicao ficam em `sources/{id}/source.png` e sao removidas apos a retencao;
os resultados ficam em `generations/{id}/result.png`.

## Observabilidade, saúde e validação manual

**Métricas.** A API expõe `GET /metrics`. O worker Celery roda com
`--max-tasks-per-child=1`, então use `PROMETHEUS_MULTIPROC_DIR` (modo
multiprocesso do prometheus_client): o diretório é configurado por
`PROMETHEUS_MULTIPROC_DIR`, limpo no `worker_init` e agregado pelo endpoint
HTTP do processo principal em `WORKER_METRICS_PORT` (padrão `9100`). O
Prometheus raspa `api:8000` e `worker:9100` (`infra/docker/prometheus`).
Rótulos são apenas de baixa cardinalidade (`kind`, `status`, `stage`,
`category`, `layer`, `locale`, `level`, `reason`); nunca prompt, e-mail, IP,
ID de usuário/geração, chave S3 ou URL assinada.

Métricas principais: gerações por kind/status e duração; duração por etapa
(`input_guard`, `assistant_llm`, `input_image_moderation`, `engine`,
`output_image_moderation`, `watermark_metadata`, `upload`, `upscale`); LLM
(outcome, latência, reparos); moderação/recusas; falhas do motor por motivo;
RAM livre/pico; créditos/cota devolvidos; penalidades; fila; SSE; upscale.
Para VRAM/temperatura não há API portátil: use HWiNFO/Adrenalin e, no futuro,
um exporter externo. A idade da tarefa mais antiga não é exposta pelo kombu
com passive declare; o alerta usa fila > 0 por 15 min.

**Saúde.** `GET /healthz` é liveness. `GET /readyz` verifica Postgres, Redis,
RabbitMQ, S3 e, em `IMAGE_ENGINE=sdcpp`, a existência do binário/modelos
(sem executá-los). LM Studio é informativo e nunca derruba o readiness.
Alertas versionados em `infra/docker/prometheus/alerts.yml`; dashboards em
`infra/docker/grafana/dashboards` (API Health e AImaginator Pipeline).

**Sentry.** Backend usa `SENTRY_DSN_BACKEND`; frontend usa
`NEXT_PUBLIC_SENTRY_DSN` via `@sentry/nextjs` (desligado com DSN vazio,
amostragem baixa). Ambos scrubam prompt, e-mail, IP, tokens, cookies, IDs,
chaves de objeto e URLs assinadas.

**Validação manual (uma etapa por vez).** Feche programas pesados e monitore
RAM/temperatura antes de cada etapa:

1. Assistente (LM Studio/Qwen): `python tools/smoke_assistant.py`
2. Moderação de imagem local: `python tools/smoke_moderation.py --folder C:/imagens`
   (você fornece as imagens; nada é gerado/baixado)
3. Geração FLUX: `python tools/smoke_sdcpp.py`
4. Edição Kontext: `python tools/smoke_sdcpp.py --edit --source entrada.png`
5. Relatório de evals: `python tools/run_evals_report.py` (gera
   `docs/agent/EVALS_REPORT.md` com acurácia, falsos bloqueios/passes e latência)

Nenhum desses scripts roda em CI nem baixa modelos automaticamente.

## Testes e Evals

O projeto usa **TDD** (pytest) e **EDD** (evals de agentes) — spec seções 6
e 21.

```bash
# Backend: testes unitários + integração (fakeredis; N+1 contra Postgres quando RUN_DB_TESTS=1)
poetry run pytest tests -q

# Evals EDD do pipeline de agentes (rubric de segurança/qualidade/latência)
poetry run pytest specs/evals -m eval -q

# Frontend: lint, vitest, build
cd apps/web && npm run lint && npm run test -- --run && npm run build
```

> O teste anti N+1 roda em CI contra Postgres real (`RUN_DB_TESTS=1`) e falha
> se qualquer query passar a emitir mais SELECTs que o esperado (spec 9.2).

## Variáveis de ambiente

Todas as credenciais vivem em `.env` (gitignored) e são lidas exclusivamente
por `infra/settings.py` (pydantic-settings). Nenhum outro arquivo chama
`os.getenv` diretamente. Veja o template completo em
[`.env.example`](./.env.example) — **nunca** coloque valores reais ali.

Grupos principais:

| Variável                  | Descrição                                              |
| ------------------------- | ------------------------------------------------------ |
| `SECRET_KEY`              | chave de assinatura dos JWTs da sessão (>= 32 chars)   |
| `DATABASE_URL`            | DSN async (`postgresql+asyncpg://...`)                 |
| `REDIS_URL`               | cache + pub/sub + rate limit store                     |
| `CELERY_BROKER_URL`       | broker RabbitMQ (`amqp://...`)                         |
| `GOOGLE_CLIENT_ID/SECRET` | credenciais OAuth (Google Cloud Console)        |
| `IMAGE_ENGINE`            | `stub` (dev/teste) ou `sdcpp` (FLUX/Kontext local via sd-cli) |
| `SDCPP_*`                 | binário e caminhos de modelo/VAE/CLIP/T5 do stable-diffusion.cpp |
| `GEN_*` / `EDIT_*`        | dimensões, steps e guidance medidos no spike      |
| `GENERATION_TIMEOUT_SECONDS` / `EDIT_TIMEOUT_SECONDS` | timeouts de 300 s/600 s |
| `EDIT_UPLOAD_MAX_BYTES` / `EDIT_UPLOAD_MAX_DIMENSION` | limites do upload de edição |
| `MIN_FREE_RAM_MB` / `COOLDOWN_SECONDS_BETWEEN_JOBS` | guarda de RAM e pausa térmica entre jobs |
| `S3_*` | endpoint, bucket, credenciais, região, expiração e retenção do storage |
| `AI_IMAGE_PROVIDER`       | legado: `stub` ou provedor HTTP externo            |
| `SENTRY_DSN_BACKEND`      | DSN do Sentry (opcional)                           |
| `ALLOWED_IMAGE_URL_DOMAINS` | allowlist anti-SSRF (separado por vírgula)       |

> Frontend: apenas `NEXT_PUBLIC_API_BASE_URL` (e DSN público do Sentry) —
> **nunca** segredos em `NEXT_PUBLIC_*`.

## Segurança

- Feature flag `FEATURE_IMAGE_GENERATION_ENABLED`: em produção o estúdio fica
  em “em breve” e os endpoints respondem `feature_disabled` até liberação.
- SSE usa ticket efêmero de uso único (Redis, TTL 60s); JWT nunca vai na URL.
- Original privado em `original.png`; somente a versão com marca/metadados é
  exposta por URL assinada.
- Upload reencodado para PNG sem EXIF, com limite de bytes/dimensão/pixels.
- Prompts do sd-cli sanitizados (controle/quebras, limite, prefixo para `-`).
- Detalhes e riscos residuais: `docs/agent/SECURITY_REVIEW.md`.



Contramedidas implementadas (spec seção 7):

| Ameaça                              | Contramedida                                                        |
| ----------------------------------- | ------------------------------------------------------------------- |
| Prompt Injection                    | `PromptInjectionGuard` (domain) + delimitadores estruturados + validação de schema |
| XSS                                 | Next.js escapa por padrão; CSP estrita; sem `dangerouslySetInnerHTML` não sanitizado |
| SQL Injection                       | SQLAlchemy com queries parametrizadas (nunca string interpolation)  |
| SSRF                                | `UrlPolicy` (allowlist/HTTPS) + validação de DNS no `SecureImageFetcher` (sem redirect, limite de bytes) |
| Buffer Overflow / payload grande    | `PayloadLimitMiddleware` (2 MB JSON; upload de edição limitado por `EDIT_UPLOAD_MAX_BYTES`) + validação Pydantic + limites no Compose |
| DDoS                                | Token Bucket na borda + rate limit por usuário + timeouts agressivos |
| Brute Force                         | SSO sem senha local + rate limit dedicado em `/auth`                 |
| Exposição no DevTools/F5            | Nenhum segredo em `NEXT_PUBLIC_*`; sourcemaps desabilitados em produção; sem stack trace ao cliente |
| Cache Stampede                      | Stale-While-Revalidate com lock `SET NX` (1 revalidação por vez)     |
| N+1                                 | Eager loading (`selectinload`/`joinedload`) + teste de contagem de queries |

## Deploy

- **Frontend (Next.js)**: Vercel, via CLI oficial (`vercel deploy`) — o job
  `deploy` do CI faz isso automaticamente em `main`.
- **Backend/workers/dados**: Docker (não roda na Vercel — serverless não
  sustenta workers Celery/RabbitMQ de longa duração). O Compose garante
  portabilidade para qualquer provedor compatível com Docker.

## CI/CD

O workflow versionado fica em `.github/workflows/ci.yml` e roda sem segredos:
ruff + pytest (sem o grupo opcional `moderation`) + evals sem LLM real,
lint/tsc/vitest/build do frontend, Playwright com backend mockado, paridade dos
11 locales e auditorias informativas (`pip-audit` e `npm audit --omit=dev`).

```bash
# local
poetry run pytest tests
poetry run pytest specs/evals -m eval
cd apps/web && npm run test && npm run test:e2e && npm run build
```

## Licenças dos modelos

Este é um projeto de portfólio. O **FLUX.1 [dev]** e o **FLUX.1 Kontext [dev]**
são distribuídos pela Black Forest Labs sob licença **não comercial**; uso
comercial exige outro modelo ou uma licença comercial da BFL. Os pesos não são
versionados neste repositório.

Os modelos de moderação usados como candidatos são
`Falconsai/nsfw_image_detection` e `openai/clip-vit-base-patch32`; consulte e
respeite a licença indicada no repositório de cada modelo (verificar a licença
no repositório do modelo antes de uso comercial).

## Decisões arquiteturais (ADRs)

- **ADR-001 — Monolito Modular + Clean Architecture por módulo.** Um único
  deployable (sem microsserviços nesta fase), mas com módulos de domínio
  fracamente acoplados e camadas internas (`domain → application → adapters →
  infra`). Motivo: os módulos viram fronteiras de contexto legíveis pelo
  GraphiFy (cada módulo = um subgrafo), o que evita vazamento de
  responsabilidades em edições futuras, e cada spec mapeia 1:1 para um caso
  de uso. Microsserviços seriam complexidade operacional desnecessária agora.

- **ADR-002 — Agentes de IA atrás de uma porta.** `ImageAgentPort` é a única
  superfície que o resto do sistema conhece; só `adapters/ai_agents/` conhece
  LangGraph (import lazy, opcional). O restante da app nao depende de CrewAI/LangChain; o pipeline tem fallback sequencial.
  de orquestração sem tocar em regra de negócio, e mantém testes/API leves
  sem as deps pesadas.

- **ADR-003 — Geração nunca é síncrona.** Toda geração/edição vai para o
  Celery (RabbitMQ), e o progresso flui por Redis Pub/Sub → SSE. Qualquer
  réplica da API serve o stream, independente de qual worker processou.

- **ADR-004 — Configuração centralizada em `infra/settings.py`.** Único ponto
  de `os.getenv`; fail-fast na subida (pydantic-settings). Nenhum outro
  arquivo lê o ambiente.

- **ADR-005 — Rate limiting com Redis compartilhado.** Token Bucket em Lua
  (atômico) para funcionar com múltiplas réplicas; Circuit Breaker e Bulkhead
  para dependências externas instáveis.

- **ADR-006 — `authlib.jose` para JWT.** Emite os tokens da sessão própria
  (não os do Google, que nunca saem do backend). Nota: `authlib.jose` está
  deprecado em favor de `joserfc` — migração prevista sem impacto funcional.

- **ADR-007 — Faixa de Python e versões das libs de IA.** `python = "^3.11"`
  foi mantido em `>=3.11,<=3.13`; a família LangChain foi alinhada à era
  0.2.x (`langchain`, `langchain-core`, `langgraph`), porque `crewai ^0.70`
  permanece apenas como dependencia transitiva do LangGraph opcional. CrewAI/LangChain diretos foram removidos. Isso garante um
  `poetry.lock` resolvível e reproduzível no runtime `python:3.11-slim`.

ADRs detalhados: `docs/agent/adr/`.

---

**Aviso de segurança**: credenciais compartilhadas em chat/prompt foram
consideradas comprometidas e **rotacionadas**:

- `SECRET_KEY` — regenerada (novo valor já no `.env`).
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — removidas do `.env`. Gere
  novas no [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
  (OAuth 2.0 Client IDs → **Reset secret**) e preencha o `.env`. Enquanto
  vazias, o SSO Google fica desabilitado (a API sobe normalmente).

## Plataforma (Fase 9)

### Status e disponibilidade
`GET /api/v1/status` e publico e informa `feature_enabled`, `maintenance` e
disponibilidade por kind (`generate`, `edit`, `upscale`). Sem worker vivo para
o kind, a criacao responde 503 `engine_offline` sem consumir credito/cota.
Cada worker publica heartbeat no Redis (id, capacidades, engine, estado,
last_seen) com TTL curto. `MAINTENANCE_MODE` ou a chave Redis
`system:maintenance` colocam a plataforma em manutencao.

### Worker remoto e motor hospedado
`WORKER_MODE=remote` permite GPU em casa falando com broker/Redis/Postgres/S3
na nuvem, exigindo TLS (`amqps`, `rediss`, `sslmode=require`) e credenciais de
menor privilegio. Ver `docs/deploy/REMOTE_WORKER.md`. `IMAGE_ENGINE=hosted`
usa um contrato HTTP simples (POST + polling) e `IMAGE_ENGINE_FALLBACK=hosted`
permite fallback quando nao ha worker local vivo.

### Guarda termica e de RAM
Com `THERMAL_GUARD_ENABLED=true`, o worker consulta `HW_SENSOR_URL`
(LibreHardwareMonitor) antes e durante o job. Acima de `START_TEMP_MAX_C`
espera resfriar; acima de `ABORT_TEMP_C` ou abaixo de `MIN_FREE_RAM_ABORT_MB`
mata a arvore do sd-cli, devolve credito/cota e fica em `cooling` por
`COOLDOWN_AFTER_ABORT_SECONDS`. Sensor ausente apenas avisa. O exporter manual
fica em `tools/hw_exporter.py`.

### Creditos, planos e uso
Todo consumo/refund/adjust passa pelo ledger `credit_ledger` com chave
idempotente e `SELECT ... FOR UPDATE`; `users.generation_credits` e o saldo
materializado. Planos `free`/`pro` configuram creditos mensais, prompts diarios
e upscale diario. O reset mensal e preguicoso e idempotente. O frontend mostra
o consumo em Configuracoes.

### Admin
`ADMIN_EMAILS` promove administradores no startup. O console em
`/[locale]/admin` permite ver usuarios sinalizados, estatisticas agregadas,
bloquear/desbloquear, ajustar creditos, ver workers, alternar manutencao e
consultar a fila de denuncias (placeholder). Toda acao grava
`admin_audit_log`; respostas nao incluem prompt, email ou IP.

### C2PA, avatar e backfill
C2PA fica no grupo opcional `provenance` (`poetry install --with provenance`).
`C2PA_REQUIRED=true` falha fechado; `false` publica sem assinatura. O avatar e
reencodado para PNG 256px, sem EXIF, gravado em `avatars/{user_id}` e servido
por proxy (sem bucket publico). Geracoes antigas sem original retornam
`original_unavailable`; o backfill manual fica em
`tools/backfill_originals.py --dry-run|--apply`.

### CI/CD e supply chain
`.github/workflows/` contem CI, CodeQL, gitleaks e auditorias com gates
High/Critical; Dependabot e build Docker (sem push) tambem estao configurados.
Excecoes de auditoria ficam em `.github/security-exceptions.json` com validade.
