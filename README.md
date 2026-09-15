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
- **SSO**: login com Google (OAuth 2.0 + OpenID Connect, Authorization Code + PKCE).

A geração de imagem **nunca** é processada de forma síncrona no request HTTP:
ela é enfileirada no Celery (RabbitMQ) e o cliente acompanha o progresso via
SSE.

## Stack tecnológica

| Camada                     | Tecnologia                                                        |
| -------------------------- | ----------------------------------------------------------------- |
| Frontend                   | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Zustand |
| i18n / a11y                | next-intl (en/pt-BR), hreflang, POUR                              |
| Backend                    | FastAPI (Python 3.11, assíncrono)                                 |
| Banco de dados             | PostgreSQL                                                         |
| ORM                        | SQLAlchemy 2.x assíncrono + Pydantic v2 + Alembic                  |
| Cache                      | Redis (Stale-While-Revalidate)                                    |
| Mensageria                 | RabbitMQ + Celery                                                  |
| Agentes de IA              | CrewAI + LangChain + LangGraph (atrás de uma porta)                |
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
                                      │ LangGraph: interpret → safety → generate/edit → post
                                      │   (CrewAI roles / LangChain parsing, atrás de porta)
                                      ▼
                              Redis Pub/Sub ──▶ FastAPI (SSE bridge) ──▶ Client (EventSource)
```

## Como rodar localmente

### Pré-requisitos

- Docker + Docker Compose (a forma mais simples — sobe tudo).
- Ou: Python 3.11 + Poetry + Node 22 (para desenvolvimento).

### 1. Subir o stack completo (Docker Compose)

```bash
cp .env.example .env   # e preencha os valores (veja Variáveis de ambiente)
docker compose -f infra/docker/docker-compose.yml up --build
```

Isso sobe: `api` (8000), `worker` (Celery), `postgres` (5432), `redis`
(6379), `rabbitmq` (5672/15672), `prometheus` (9090) e `grafana` (3001).

### 2. Frontend (Next.js)

O frontend roda separadamente (Vercel é serverless; ver Deploy):

```bash
cd apps/web
npm install
npm run dev            # http://localhost:3000
```

### 3. Backend (sem Docker, para desenvolvimento)

```bash
poetry install --with dev
poetry run alembic upgrade head
poetry run uvicorn apps.api.main:app --reload          # API em :8000
poetry run celery -A workers.celery_app.celery:celery_app worker --loglevel=info  # worker
```

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
| `GOOGLE_CLIENT_ID/SECRET` | credenciais OAuth (Google Cloud Console)               |
| `AI_IMAGE_PROVIDER`       | `stub` (dev/teste) ou provedor real                    |
| `SENTRY_DSN_BACKEND`      | DSN do Sentry (opcional)                               |
| `ALLOWED_IMAGE_URL_DOMAINS` | allowlist anti-SSRF (separado por vírgula)           |

> Frontend: apenas `NEXT_PUBLIC_API_BASE_URL` (e DSN público do Sentry) —
> **nunca** segredos em `NEXT_PUBLIC_*`.

## Segurança

Contramedidas implementadas (spec seção 7):

| Ameaça                              | Contramedida                                                        |
| ----------------------------------- | ------------------------------------------------------------------- |
| Prompt Injection                    | `PromptInjectionGuard` (domain) + delimitadores estruturados + validação de schema |
| XSS                                 | Next.js escapa por padrão; CSP estrita; sem `dangerouslySetInnerHTML` não sanitizado |
| SQL Injection                       | SQLAlchemy com queries parametrizadas (nunca string interpolation)  |
| SSRF                                | `UrlPolicy` (allowlist/HTTPS) + validação de DNS no `SecureImageFetcher` (sem redirect, limite de bytes) |
| Buffer Overflow / payload grande    | `PayloadLimitMiddleware` (2 MB) + validação Pydantic + limites no Compose |
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

`infra/github/workflows/ci.yml` — pipeline com estágios:

```
gitleaks (secrets) → lint (ruff) → test (pytest, Postgres+Redis reais)
                   → eval (EDD) → frontend (eslint/vitest/build) → deploy (Vercel)
```

Falha em qualquer estágio bloqueia o merge (branch protection). O Docker
Compose orquestra o ambiente completo localmente.

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
  CrewAI/LangChain/LangGraph (imports lazy). Isso permite trocar o framework
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

---

**Aviso de segurança**: credenciais compartilhadas em chat/prompt devem ser
consideradas comprometidas. Rotacione `GOOGLE_CLIENT_SECRET` e `SECRET_KEY`
antes de subir para produção.
