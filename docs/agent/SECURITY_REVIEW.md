# Revisão de segurança — AImaginator

Data: 2026-11-06. Escopo: API, worker, frontend, storage, runtime local e
dependências. Nenhum modelo real foi executado.

## Correções aplicadas

| Severidade | Achado | Correção |
|---|---|---|
| Alta | JWT de acesso ia na query string do EventSource (logs/histórico) | Ticket efêmero single-use no Redis (TTL 60s), vinculado à geração e ao solicitante; frontend troca ticket por stream |
| Alta | Produção podia iniciar geração sem validação de host/modelos | `FEATURE_IMAGE_GENERATION_ENABLED` (false em produção por padrão), `feature_disabled` 503 e `/config` para o frontend |
| Alta | Dependências com CVEs conhecidas | Pillow 13, Authlib 1.9.1, aiohttp 3.14.4, certifi/joserfc atualizados; Next.js 16.4.5; `pip-audit` e `npm audit --omit=dev` limpos |
| Média | Prompt poderia ser interpretado como opção do sd-cli | `sanitize_prompt_argument`: controle/quebras removidos, limite 2000, prefixo de espaço para `-`; teste com executável falso que registra argv |
| Média | Upload sem limite de pixels e preservando metadados | `Image.MAX_IMAGE_PIXELS`, validação de pixels, `verify()`, reencode PNG sem EXIF/metadados, temp dirs aleatórios com permissão 700 no POSIX |
| Média | TokenBucket usava `time.monotonic()` em estado Redis compartilhado | Lua usa `redis.call('TIME')`; teste com relógio monotônico local divergente |
| Média | IDOR em detalhe/histórico/variação/refino/upscale/stream | Ownership em use cases e ticket; testes A/B, 403 e ausência de `original_object_key` na resposta |
| Média | Scrubber Sentry incompleto | Mensagens, exceções, breadcrumbs, request, extras/tags/contextos, e-mail, IP, tokens, IDs, chaves e URLs assinadas |
| Média | CORS/CSP/headers | CORS restrito à origem configurada; CSP Next com storage; HSTS em produção; headers de segurança no backend |
| Baixa | Gerações antigas sem original causavam erro 500/422 genérico | `original_unavailable` (409) localizado em refino/upscale |
| Baixa | URLs assinadas longas | Expiração configurável (`S3_PRESIGN_EXPIRES_SECONDS`, padrão 900s), sem logs de URL/credencial |

## Verificações

- `SecureImageFetcher`: HTTPS, allowlist, DNS anti-SSRF, redirect bloqueado,
  limite de bytes e timeout; URL só passa por ele no fluxo de edição por URL.
- `sd-cli`: argv em lista, sem shell, prompt sanitizado, timeout por kind,
  kill da árvore, temp dir aleatório e limpeza.
- Stream: ticket aleatório de 32 bytes, single-use (`GET` + `DEL` atômico),
  TTL 60s, vínculo à geração/principal; JWT não aparece mais na URL.
- Sentry backend/frontend desligado com DSN vazio; amostragem baixa.
- Migrations são aditivas; downgrade remove apenas o que a migration criou.
- `/readyz` verifica Postgres, Redis, RabbitMQ, S3 e arquivos do sdcpp; LM
  Studio é aviso não bloqueante.

## Auditorias

- `pip-audit --local` (2026-11-09): **3 vulnerabilidades conhecidas em 2
  pacotes**: `langsmith` 1 (transitiva do LangGraph opcional) e
  `pytest` 2 (dev), ambos com exceção datada em
  `.github/security-exceptions.json`. FastAPI/Starlette/LangGraph foram
  atualizados para versões sem High/Critical. Foram removidos `crewai` e
  `langchain` diretos e 164 pacotes transitórios; o total caiu de 279/30 para 3/2. `python-multipart` subiu 0.0.9 -> 0.0.33; `urllib3`, `pyjwt` e
  `multidict` foram atualizados.
- `npm audit --omit=dev`: **0 vulnerabilidades de produção**.
- `npm audit` completo: 8 moderadas de ferramentas de desenvolvimento
  (`typescript-eslint`/`vite` transitivos); correção exigiria upgrade major
  fora do escopo, aceito como risco de desenvolvimento.

## Riscos aceitos / pendências

- LM Studio local sem autenticação forte; deve ficar em rede local/loopback.
- C2PA desligado até existir certificado de CA confiável.
- Pesos FLUX/Kontext não são versionados; licença FLUX dev é não comercial.
- Revisão das traduções por falantes nativos e calibração de limiares com
  modelos reais continuam manuais.

## Revisao Fase 7.5/7.6 (assistente, fila e ambiente)

Data: 2026-11-08. Escopo adicional: cliente LLM, fila Celery, reconciliacao,
ambiente de desenvolvimento e qualidade da reescrita.

| Severidade | Achado | Correcao |
|---|---|---|
| Alta | Reasoning do Qwen consumia `max_tokens` e devolvia `content` vazio, virando `assistant_unavailable` sem causa visivel | `reasoning_effort=none` no topo do payload; retry unico com `max_tokens` maior; `reasoning_content` nunca e usado como resposta nem exposto; logs guardam apenas tamanhos |
| Alta | Broker/Redis remotos podiam ser usados silenciosamente em `APP_ENV=development` | Guarda de infra local no startup da API/worker; hosts remotos falham salvo `ALLOW_REMOTE_INFRA_IN_DEV=true`; `.env.development` tem precedencia e o `.env` de producao nao e carregado nesse modo |
| Alta | Falha de publish deixava a Generation em `queued` para sempre; worker perdido podia perder a task | `task_acks_late`/`task_reject_on_worker_lost`; enqueue que falha marca `queue_publish_failed` com refund; reconciliador `queue_lost` por inatividade; heartbeat commitado por etapa |
| Media | Categoria de bloqueio vinha do campo do modelo e podia trocar sexual por self_harm | Categoria derivada dos booleanos com prioridade sexual > hate > gore > self_harm; divergencia registrada em metrica sem texto; self_harm so aparece quando e a categoria final |
| Media | Reescrita adicionava enfeites/negacoes e podia induzir o FLUX a desenhar o conteudo negado | Regras no system prompt + reparo unico deterministico + sanitizacao sem falhar o job; "Keep everything else the same" permitido |
| Media | Preview de conteudo do LLM em log podia expor prompt/reescrita | `content_preview`/`raw_preview` removidos por padrao; somente com `LLM_DEBUG_LOG_CONTENT=true` em development, truncados e com scrubber |
| Baixa | Modelo do LM Studio permanecia carregado durante o FLUX, pressionando RAM | `lms unload --all` opcional antes do motor, sem shell, com timeout; falha apenas gera aviso/metrica |

Verificacoes adicionais: logs de categoria/reescrita sem texto; nenhum
`reasoning_content` no contrato publico; testes com LLM falso e fila falsa;
`pytest tests`, `pytest specs/evals`, vitest, Playwright, ruff, lint e tsc
verdes. Riscos aceitos continuam os da secao anterior (LM Studio sem auth
forte, C2PA desligado, calibracao/traducao manuais).

## Varredura de segredos e arquivos grandes (2026-11-08)

- Nenhum `.env`, `.env.local` ou `.env.development` real esta rastreado ou no
  historico local; apenas os `*.example`.
- Nenhuma chave `sk-`, `AIza`, `AKIA`, `Bearer`, chave privada ou DSN com
  credenciais foi encontrada no working tree ou no historico.
- O unico match de `SECRET_KEY` e um placeholder de exemplo em `.env.example`
  (sem valor real); o teste `test_dev_guard.py` usa uma URL ficticia com
  senha apenas para validar o mascaramento.
- Nenhum blob versionado maior que 5 MB; nenhum modelo/peso ou imagem de teste
  novo. A logo em `modules/image_generation/assets/` e o unico asset de imagem
  de backend versionado.
- `crewai` e `langchain` diretos foram removidos do `pyproject.toml`; o
  `poetry.lock` tambem removeu 164 pacotes transitivos. `langgraph` permanece
  opcional/lazy, com fallback sequencial.

## Revisao Fase 9 (plataforma)

- Workers remotos exigem `WORKER_MODE=remote`, TLS em broker/Redis/Postgres e
  credenciais de menor privilegio; ver `docs/deploy/REMOTE_WORKER.md`.
- Guarda termica/RAM aborta jobs, mata a arvore do sd-cli e coloca o worker em
  `cooling`; sem sensor apenas avisa.
- Ledger de creditos com `SELECT ... FOR UPDATE`, idempotencia e reset mensal;
  ajustes administrativos auditados sem prompt/email.
- Avatar sai do banco e vai para S3 via proxy, sem bucket publico/URL assinada.
- C2PA e opcional no grupo `provenance`; `C2PA_REQUIRED=true` falha fechado.
- CI ganhou Dependabot, CodeQL, gitleaks, gates de auditoria e build Docker.
- Varredura de segredos permanece limpa; nenhum `.env`/modelo/imagem de teste
  novo e nenhum blob > 5 MB.


## Fase 10 - links publicos e denuncias

- Tokens de compartilhamento tem 256 bits, sao armazenados como SHA-256 (nunca
  em claro), revogaveis/expirados e entregam apenas a versao com marca d'agua
  via presign curto. Prompt so aparece com `allow_prompt=true`.
- Imagem oculta/removida invalida links; respostas publicas nao expoem dono,
  email, IDs internos ou `original_object_key`.
- Denuncias tem rate limit por usuario/IP e fila admin auditada
  (`hide`, `remove_link`, `penalty`, `discard`).
- Riscos residuais: token na URL pode aparecer em referrer/historico do
  navegador; abuse de denuncias exige calibracao; UI completa de biblioteca e
  notificacoes ainda pendente.
