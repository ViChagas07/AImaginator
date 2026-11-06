# FASE 0 — Diagnóstico (somente leitura) — AImaginator

> Data da inspeção: 2026-11-05
> Repositório: `C:\Users\Alisson Davi\AImaginator`
> Branch/commit: `main` @ `9066aa5`
> Escopo: leitura e comandos de inspeção. Nenhum código foi alterado, nenhum commit/push foi feito.
> Única escrita desta fase: este relatório em `docs/agent/FASE0_REPORT.md`, conforme solicitado.

---

## 0. Resumo executivo

- O fluxo assíncrono de geração existe e está bem separado em camadas: rota → caso de uso → fila Celery → orquestrador → SSE.
- **Não existe geração real de imagem integrada.** O caminho padrão é `StubImageProvider` (URL de placeholder). O caminho “real” é um `HttpImageProvider` genérico que chama `POST {base}/v1/images/generations` de um provedor externo fictício; não há FLUX, Kontext, ComfyUI, diffusers ou stable-diffusion.cpp no backend.
- O guardrail de escopo em duas camadas existe: `PromptTopicGuard` (classificador LLM) + `ScopeGuardrail` determinístico no orquestrador. A mensagem fixa de recusa existe. Os testes específicos do guardrail de tópico passaram (11/11), mas a suíte total tem 1 falha em um teste property-based do `PromptInjectionGuard` (falso positivo com a palavra `JAILBREAK`, que a guarda rejeita por design).
- O `PromptInjectionGuard` está ligado às duas rotas de geração/edição (`POST /api/v1/generations` e `POST /api/v1/generations/edits`).
- Não há integração específica com LM Studio. Existe apenas um classificador genérico “OpenAI Chat Completions” (`HttpPromptClassifier`) que poderia apontar para `http://localhost:1235/v1`, mas ele só classifica escopo; não modera, não reescreve prompts e não traduz para 11 idiomas.
- O frontend tem **9 locales**, não 11, e somente `pt-BR` e `en` têm o conjunto completo de chaves (288 chaves); os outros 7 têm 138 chaves (faltam 150).
- O backend não recebe o idioma atual do site nas requisições de geração/edição: locale só existe em `user_settings` via `PUT /api/v1/users/me/settings`.
- Há incompatibilidades de contrato entre frontend e backend: `image` enviado pelo frontend vs. `source_image_url` esperado no backend; `percent` vs. `progress`; `imageUrl` vs. `result_image_url`; `cursor` vs. `next_cursor`.
- O `.env` atual está configurado como **produção** (`APP_ENV=production`) e aponta para Render/Upstash/CloudAMQP, não para um ambiente local. O `.env.local` do frontend aponta para o Render.
- Hardware: Windows 11, Ryzen 7 5800X, 15,93 GB de RAM total (~0,8–1,5 GB livres durante a inspeção), GPU AMD Radeon RX 6500 XT com **~8 GB de VRAM dedicada** (dxdiag: 8146 MB; heap Vulkan `DEVICE_LOCAL`: 7,98 GiB), driver AMD 25.9.2/Vulkan 1.4.315. Não há CUDA/NVIDIA. O valor de 4 GB do WMI `AdapterRAM` é um artefato de campo de 32 bits e não deve ser usado.
- Há apenas o GGUF `flux1-dev-Q5_K_S.gguf` (7,72 GiB) registrado no LM Studio. Não foram encontrados arquivos de FLUX Kontext, T5, CLIP ou VAE nas localizações inspecionadas.
- O LM Studio responde em `http://localhost:1235/v1/models`, mas **nenhum modelo está carregado** (`state: not-loaded`).

---

## 1. Orquestrador e módulo de imagem

### 1.1 Existe: fluxo atual de ponta a ponta

**Rota → caso de uso → fila**

- `POST /api/v1/generations` em `apps/api/routers/generations.py:47-84`.
  - Usuário autenticado: `limiter.consume` e `ConsumePromptQuota` antes de chamar `GenerateImageFromPrompt` (`generations.py:62-72`).
  - Usuário anônimo: resolve a sessão assinada, aplica limite/quota e chama `GenerateImageAnonymous` (`generations.py:74-84`).
- `POST /api/v1/generations/edits` em `apps/api/routers/generations.py:87-112`.
  - Exige usuário autenticado (`CurrentUserDep`), aplica token bucket e chama `EditImageFromPrompt`. **Não** consome a cota diária de prompts (`generations.py:103-112`).
- `GenerateImageFromPrompt.execute` em `modules/image_generation/application/use_cases/generate_image.py:52-74`:
  1. `PromptInjectionGuard.validate` (`generate_image.py:53`);
  2. `PromptTopicGuard.validate` (`generate_image.py:54`);
  3. valida negative prompt, se houver (`generate_image.py:55-57`);
  4. `user.consume_credit()` (`generate_image.py:59`);
  5. salva `Generation` como `QUEUED` (`generate_image.py:62-71`);
  6. enfileira a task (`generate_image.py:72`);
  7. devolve `GenerationOutput` com `stream_url` (`generate_image.py:74`).
- `GenerateImageAnonymous.execute` em `generate_image.py:93-114` faz o mesmo, mas sem usuário/credito e com `anonymous_session_id`.
- `EditImageFromPrompt.execute` em `modules/image_generation/application/use_cases/edit_image.py:33-68` valida prompt/tópico, valida a URL de origem com `UrlPolicy`, debita credito do usuário, salva e enfileira.

**Worker → orquestrador**

- `workers/celery_app/tasks.py:29-62` monta o wiring do worker: `build_prompt_guard`, `build_image_provider`, `build_image_agent`, `ProcessGeneration`.
- `modules/image_generation/application/use_cases/process_generation.py:35-67`:
  - carrega a geração;
  - transita para `PROCESSING`;
  - publica progresso inicial 5 (`process_generation.py:53`);
  - chama `agent.run_generation` (`process_generation.py:58`);
  - em sucesso, `attach_result` e publica `DONE` com `result_image_url` (`process_generation.py:60-62`);
  - em falha, transita para `FAILED` e publica `error` (`process_generation.py:63-66`).

**Orquestrador**

- `modules/image_generation/adapters/ai_agents/orchestrator.py:1-16` descreve o pipeline: `interpret_prompt → safety_check → scope_check → generate_or_edit → post_process`.
- O grafo LangGraph é montado em `orchestrator.py:126-144`; se `langgraph` não estiver instalado, o fallback sequencial equivalente roda em `orchestrator.py:159-169`.
- `_interpret_prompt` (`orchestrator.py:68-83`) **não chama nenhum LLM**: apenas envolve o prompt em delimitadores `<<<USER_PROMPT_BEGIN>>>...<<<USER_PROMPT_END>>>` e anexa o `style_preset`.
- `_safety_check` (`orchestrator.py:85-89`) chama novamente `PromptInjectionGuard.validate`.
- `_scope_check` (`orchestrator.py:91-101`) chama `ScopeGuardrail.check`.
- `_generate_or_edit` (`orchestrator.py:103-114`) chama `self._provider.generate(generation, noop_progress)`.
- `_post_process` (`orchestrator.py:116-122`) apenas verifica se a URL começa com `https://` ou `http://`.
- `run_generation` (`orchestrator.py:148-157`) chama o grafo/fallback e depois `on_progress(95)`.

**SSE**

- `GET /api/v1/generations/{id}/stream` em `apps/api/routers/stream.py:43-104`.
- O worker publica no Redis Pub/Sub via `RedisEventPublisher` (`modules/image_generation/adapters/redis_event_publisher.py:11-17`).
- O endpoint se inscreve no canal e repassa os eventos (`stream.py:76-99`).
- O frontend consome com `EventSource` em `apps/web/stores/generation.ts:101-127`.

### 1.2 Existe: stub/mock e modelos chamados

- **Stub de imagem:** `StubImageProvider` em `modules/image_generation/adapters/ai_agents/providers.py:26-44`. Gera uma URL determinística de `picsum.photos` a partir do hash do prompt; não gera imagem.
- **Provedor HTTP genérico:** `HttpImageProvider` em `providers.py:47-95` chama `POST {base}/v1/images/generations` (`providers.py:67-78`) e espera `image_url` ou `image_base64` (`providers.py:88-95`). Se receber `image_base64`, levanta erro porque não há storage próprio (`providers.py:90-92`).
- **Stub de classificador:** `StubPromptClassifier` em `modules/image_generation/adapters/ai_agents/prompt_classifier.py:61-67`. Trata todo prompt como relacionado a imagem.
- **Classificador HTTP OpenAI-compatível:** `HttpPromptClassifier` em `prompt_classifier.py:70-117`; chama `{base}/chat/completions` (`prompt_classifier.py:87-99`).
- **Classificador Gemini nativo:** `GeminiPromptClassifier` em `prompt_classifier.py:120-192`; usa o endpoint nativo do Gemini.
- **Nenhum modelo de imagem local é chamado.** O único caminho “real” de imagem é o HTTP genérico acima; o `.env` atual aponta para `https://api.exemplo-provedor.com` (placeholder), portanto uma geração real falharia.
- **Nenhum LLM é chamado no orquestrador.** O único LLM possível no fluxo é o classificador de tópico da Camada 1 (Gemini ou HTTP OpenAI-compatível), chamado antes do enfileiramento, no request.

### 1.3 Portas/interfaces definidas

| Porta/interface | Onde está | Implementações concretas |
|---|---|---|
| `ImageAgentPort` (`run_generation`) | `modules/image_generation/application/ports/image_agent_port.py:19-27` | `LangGraphImageAgent` (`adapters/ai_agents/orchestrator.py:50`) |
| `ImageProvider` (`generate`) | `modules/image_generation/adapters/ai_agents/providers.py:20-23` | `StubImageProvider`, `HttpImageProvider` |
| `IPromptClassifier` (`classify`) | `modules/image_generation/domain/prompt_topic_guard.py:38-43` | `StubPromptClassifier`, `HttpPromptClassifier`, `GeminiPromptClassifier` |
| `IPromptTopicGuard` (`validate`) | `domain/prompt_topic_guard.py:46-51` | `PromptTopicGuard` |
| `ImageFetcherPort` (`fetch`, `fetch_base64_data_url`) | `application/ports/image_fetcher.py:8-18` | `SecureImageFetcher` (`adapters/secure_image_fetcher.py:28-71`) — **não é usado no wiring atual** |
| `TaskQueuePort` | `application/ports/task_queue.py:9-12` | `CeleryTaskQueue` |
| `EventPublisherPort` | `application/ports/event_publisher.py` | `RedisEventPublisher` |
| `GenerationRepositoryPort` | `application/ports/generation_repository.py:11` | `SQLAlchemyGenerationRepository` |

**NÃO EXISTE** uma porta `ImageGenerator` ou `ImageEditor` separada. O mesmo `ImageProvider.generate` atende geração e edição; o tipo (`generate`/`edit`) só é usado para logging (`orchestrator.py:106`) e para o payload HTTP (`providers.py:70-75`).

### 1.4 Riscos/inconsistências do item 1

- O `SCOPE_GUARDRAIL_PROMPT` é construído e guardado em `state["scope_system_prompt"]` (`orchestrator.py:63`, `81`), mas **nunca é enviado a nenhum LLM**. O nome “system prompt do orquestrador” existe como template, mas não está em uso real.
- O orquestrador não interpreta, modera ou reescreve o prompt: `_interpret_prompt` é apenas concatenação de delimitadores.
- O `noop_progress` em `orchestrator.py:109-111` não chama o callback real; o progresso do provider é descartado. O SSE só recebe `processing 5` e depois `95`/`100` (`process_generation.py:53-62`).
- `_post_process` aceita qualquer URL HTTP(S); não valida conteúdo, tipo MIME, existência ou tamanho da imagem.
- `HttpImageProvider` não consegue persistir `image_base64`; um adapter local de FLUX que devolva base64 precisará de storage/serving antes de funcionar.
- O worker recria `httpx.AsyncClient`, Redis e o agente a cada task (`tasks.py:44-62`); não há cache/persistência do modelo local entre tasks.
- O `SecureImageFetcher` está implementado mas não é usado por nenhum use case/wiring; edição por URL não baixa a imagem no backend, apenas repassa a URL ao provedor.

---

## 2. Guardrail de escopo (confirmação)

### 2.1 Existe: Camada 1 — `PromptTopicGuard`

- Implementação: `modules/image_generation/domain/prompt_topic_guard.py:54-92`.
- Porta do classificador: `IPromptClassifier` em `prompt_topic_guard.py:38-43`.
- Porta usada pelos use cases: `IPromptTopicGuard` em `prompt_topic_guard.py:46-51`.
- Regras:
  - confiança mínima `0.6` (`prompt_topic_guard.py:23`);
  - timeout de 4 s (`prompt_topic_guard.py:26`);
  - `asyncio.wait_for` com fail-closed em timeout (`prompt_topic_guard.py:75-80`);
  - qualquer exceção do classificador vira `InvalidPromptTopicError` (`prompt_topic_guard.py:80-83`);
  - exige `is_image_related=True`, confiança >= 0.6 e `cleaned_prompt` não vazio (`prompt_topic_guard.py:85-91`);
  - devolve `cleaned_prompt`, que é a parte de imagem extraída/reescrita pelo classificador (`prompt_topic_guard.py:92`).
- System prompt do classificador: `TOPIC_CLASSIFIER_SYSTEM_PROMPT` em `prompt_classifier.py:23-36`. Ele pede JSON estrito com `is_image_related`, `cleaned_prompt` e `confidence`.
- O caso de uso usa o resultado: `clean_prompt = await self._topic_guard.validate(clean_prompt)` em `generate_image.py:54` e `edit_image.py:35`.
- O classificador é montado em `modules/image_generation/infra/wiring.py:39-66`:
  - `stub` ou chave vazia → `StubPromptClassifier` (`wiring.py:42-44`);
  - `gemini` → `GeminiPromptClassifier` (`wiring.py:45-50`);
  - default → `HttpPromptClassifier` (`wiring.py:51-57`).

### 2.2 Existe: Camada 2 — `ScopeGuardrail` determinístico

- Implementação: `modules/image_generation/adapters/ai_agents/guardrails.py:136-161`.
- Sinais de imagem PT/EN: `guardrails.py:49-88`.
- Sinais de pedido textual/analítico: `guardrails.py:96-133`.
- Regra: recusa somente quando há sinal de fora de escopo **e** não há sinal de imagem (`guardrails.py:156-161`), levantando `OutOfScopeError`.
- O orquestrador chama `self._scope_guardrail.check(...)` em `orchestrator.py:91-101`.
- O template de system prompt endurecido existe em `guardrails.py:20-39` e `build_scope_system_prompt` em `guardrails.py:42-44`, mas não é enviado a LLM (ver item 1.4).

### 2.3 Existe: mensagem fixa de recusa

- `SCOPE_REFUSAL_MESSAGE` em `shared_kernel/security_errors.py:10-14`.
- `InvalidPromptTopicError` usa essa mensagem por padrão (`security_errors.py:21-27`).
- `OutOfScopeError` usa essa mensagem por padrão (`security_errors.py:30-36`).
- O `PromptInjectionDetectedError` (`security_errors.py:17-18`) tem mensagem própria e código `prompt_rejected`.
- A recusa de escopo ocorre antes de qualquer chamada ao provedor de imagem; portanto, não gasta tokens do modelo de imagem. Entretanto, a Camada 1 pode gastar uma chamada ao LLM classificador.

### 2.4 Existe: extração da parte de imagem em prompts mistos

- A extração é delegada ao classificador via `cleaned_prompt` (`prompt_classifier.py:34-35`, `prompt_topic_guard.py:85-92`).
- O teste `test_prompt_misto_extrai_apenas_parte_de_imagem` cobre o comportamento com um classificador fake (`tests/unit/test_prompt_topic_guard.py:121-135`).
- Não há teste com o `HttpPromptClassifier`/`GeminiPromptClassifier` reais (sem `respx`/mock HTTP).

### 2.5 Existe: PromptInjectionGuard nas rotas

- `PromptInjectionGuard` em `modules/image_generation/domain/prompt_guard.py:42-62`.
- `PromptGuardDep` é injetado em `create_generation` (`apps/api/routers/generations.py:56`) e em `create_edit` (`generations.py:98`).
- Os use cases chamam a guarda antes do classificador: `generate_image.py:53`, `edit_image.py:34`.
- O worker revalida no orquestrador: `orchestrator.py:85-89`.

### 2.6 Testes executados

| Comando | Resultado |
|---|---|
| `pytest tests/unit/test_prompt_topic_guard.py` | **11 passed** |
| `pytest tests/unit/test_prompt_quota.py` | **6 passed** |
| `pytest tests/unit/test_prompt_guard.py` | **21 passed, 1 failed** |
| `pytest specs/evals -m eval` | **4 passed** |
| `pytest tests` | **1 failed, 122 passed, 1 skipped** |

A falha é `tests/unit/test_prompt_guard.py::test_property_prompts_benignos_nunca_sao_rejeitados` (`tests/unit/test_prompt_guard.py:75-80`). O Hypothesis gerou o texto `JAILBREAK`, que é rejeitado pelo padrão `r"jailbreak"` em `prompt_guard.py:33`. É um falso positivo do teste de propriedade (a guarda rejeita “jailbreak” por design), não uma brecha do guardrail.

### 2.7 Riscos/inconsistências do item 2

- **Cota consumida antes da validação:** a rota consome `ConsumePromptQuota` e o token bucket antes de chamar o use case, que só então roda `PromptInjectionGuard` e `PromptTopicGuard` (`generations.py:62-72`, `74-84`). Portanto, um prompt recusado por injeção/escopo **queima a chance diária** do usuário. Não há teste cobrindo essa ordem.
- **Edição não consome a cota diária:** `create_edit` só chama `limiter.consume`, não `ConsumePromptQuota` (`generations.py:103-112`). O limite de 1/3 por 24h não se aplica a edições; só o token bucket de 10/min e os créditos do usuário.
- **Dois sistemas de cota:** `User.generation_credits` (50 por padrão, persistido, debitado em `generate_image.py:59` e `edit_image.py:38`) e a cota Redis de 1/3 por 24h (`prompt_quota`). Não há reset mensal implementado para `generation_credits`.
- **Mensagem fixa não chega ao usuário:** o backend devolve `{"error":{"code","message"}}` (`apps/api/main.py:132-142`), mas o frontend, em erro HTTP, mostra apenas `errors.http(status)` (`apps/web/stores/generation.ts:85-87`). No SSE, o backend publica o campo `error` (`process_generation.py:66`), enquanto o frontend lê `payload.message` (`generation.ts:116-126`). A recusa de escopo é, na prática, substituída por uma mensagem genérica localizada.
- **Cobertura PT/EN apenas:** os padrões de injeção são predominantemente em inglês (`prompt_guard.py:21-36`); não há padrões equivalentes em PT, ES, FR, DE, JA, ZH, RU, AR. Os sinais lexicais da Camada 2 também são PT/EN (`guardrails.py:49-133`). Em outros idiomas, a Camada 2 pode falhar aberta; a Camada 1 é a única defesa semântica.
- **System prompt só em PT:** o `TOPIC_CLASSIFIER_SYSTEM_PROMPT` está em português (`prompt_classifier.py:23-36`); não há versões em 11 idiomas nem instrução explícita de tradução.
- **Classificador recebe prompt cru:** `HttpPromptClassifier` manda o prompt do usuário diretamente como mensagem `user` (`prompt_classifier.py:86-99`), sem delimitadores estruturados. O orquestrador usa delimitadores, mas o classificador não.
- **Sem moderação de conteúdo:** o `SafetyReviewerAgent` (`orchestrator.py:85-89`) só roda o `PromptInjectionGuard`; não há classificador NSFW/violência/legal. “Moderar” não está implementado.
- **Sem auditoria:** não há tabela/serviço de tentativas bloqueadas; as recusas só geram resposta HTTP e, no máximo, logs. Não há registro estruturado com idioma, prompt, camada, confiança e principal.

---

## 3. LLM local (LM Studio / OpenAI-compatível)

### 3.1 Existe

- **Cliente HTTP genérico OpenAI-compatível:** `HttpPromptClassifier` em `modules/image_generation/adapters/ai_agents/prompt_classifier.py:70-117`.
  - URL: `{api_base_url}/chat/completions` (`prompt_classifier.py:87-88`).
  - Corpo: `model`, `temperature: 0`, mensagens `system` + `user` (`prompt_classifier.py:89-96`).
  - Header: `Authorization: Bearer {api_key}` (`prompt_classifier.py:97`).
  - Timeout HTTP: 5 s (`prompt_classifier.py:98`); o `PromptTopicGuard` impõe 4 s (`prompt_topic_guard.py:26`, `75-77`).
- **Configuração via settings:** `topic_classifier_provider`, `topic_classifier_api_key`, `topic_classifier_api_base_url`, `topic_classifier_model`, `topic_classifier_timeout_seconds` em `infra/settings.py:69-75`.
- **Variáveis no `.env.example`:** `TOPIC_CLASSIFIER_PROVIDER`, `TOPIC_CLASSIFIER_API_KEY`, `TOPIC_CLASSIFIER_API_BASE_URL`, `TOPIC_CLASSIFIER_MODEL`, `TOPIC_CLASSIFIER_TIMEOUT_SECONDS` (`.env.example:51-60`).
- **LM Studio está acessível:** `GET http://localhost:1235/v1/models` retornou HTTP 200 com:
  - `flux.1-dev` (`arch: flux`, `quantization: Q5_K_S`, `state: not-loaded`);
  - `qwen/qwen3.5-9b` (`type: vlm`, `Q4_K_M`, `state: not-loaded`, contexto máximo 262144);
  - `text-embedding-nomic-embed-text-v1.5` (`type: embeddings`, `state: not-loaded`).
- **Config do servidor LM Studio:** porta `1235`, host `127.0.0.1`, `autoStartOnLaunch: true`, `justInTimeModelLoading: true` (`C:\Users\Alisson Davi\.lmstudio\apps\bionic\.internal\http-server-config.json`).

### 3.2 NÃO EXISTE

- **NÃO EXISTE** variável `LM_STUDIO_*`, `LOCAL_LLM_*` ou similar no backend nem no `.env.example`.
- **NÃO EXISTE** integração específica com LM Studio; o código não menciona “LM Studio”.
- **NÃO EXISTE** cliente OpenAI oficial no projeto: `openai` não está em `pyproject.toml` (dependências em `pyproject.toml:20-46`); o classificador usa `httpx` cru. O `openai` existe apenas no Python global 3.14, fora do `.venv` do projeto.
- **NÃO EXISTE** LLM para moderação de conteúdo.
- **NÃO EXISTE** LLM para reescrever/traduzir prompts. O `cleaned_prompt` do classificador é a única “reescrita”, e não é tradução.
- **NÃO EXISTE** chamada de LLM no orquestrador; `_interpret_prompt` não chama modelo (`orchestrator.py:68-83`).

### 3.3 Estado atual do `.env` (sem expor segredos)

O arquivo `.env` existe (não versionado). Inspeção apenas de nomes/valores não secretos:

| Variável | Valor atual observado |
|---|---|
| `APP_ENV` | `production` |
| `AI_IMAGE_PROVIDER` | `http` |
| `AI_IMAGE_API_BASE_URL` | `https://api.exemplo-provedor.com` (placeholder) |
| `TOPIC_CLASSIFIER_PROVIDER` | `gemini` |
| `TOPIC_CLASSIFIER_MODEL` | `gemini-1.5-flash` |
| `TOPIC_CLASSIFIER_API_BASE_URL` | vazio |
| `STORAGE_BUCKET_URL` | `https://cdn.seu-proprio-bucket.com` |
| `ALLOWED_IMAGE_URL_DOMAINS` | `images.unsplash.com,cdn.seu-proprio-bucket.com` |
| `NEXT_PUBLIC_API_BASE_URL` | `https://aimaginator.onrender.com` |
| `API_BASE_URL` | `https://aimaginator.onrender.com` |
| `FRONTEND_BASE_URL` | `https://aimaginator.vercel.app` |

As chaves `AI_IMAGE_API_KEY`, `TOPIC_CLASSIFIER_API_KEY` e `GEMINI_API_KEY` estão preenchidas; valores omitidos. Os DSNs de Sentry estão vazios.

### 3.4 Riscos/inconsistências do item 3

- Para usar LM Studio no classificador, seria necessário configurar `TOPIC_CLASSIFIER_PROVIDER=http`, `TOPIC_CLASSIFIER_API_BASE_URL=http://localhost:1235/v1`, `TOPIC_CLASSIFIER_MODEL=<id do modelo>` e uma `TOPIC_CLASSIFIER_API_KEY` não vazia (o wiring cai em stub se a chave estiver vazia: `wiring.py:42-44`). O LM Studio normalmente aceita qualquer token, mas o código exige string não vazia.
- O `.env` atual usa Gemini, não LM Studio; `TOPIC_CLASSIFIER_API_BASE_URL` está vazio, então o caminho `http` não está ativo.
- O LM Studio está com **nenhum modelo carregado**; a geração de imagem via FLUX não está pronta para uso imediato.
- Não há garantia de que o LM Studio exponha `/v1/images/generations` para o GGUF FLUX; o backend também não chama esse endpoint no LM Studio.
- O `HttpPromptClassifier` manda `Authorization` mesmo para LM Studio; se o servidor local exigir outro esquema, pode falhar.

---

## 4. I18N

### 4.1 Existe

- Locales no frontend: `apps/web/i18n/routing.ts:3-5` define **9 locales**:
  `pt-BR`, `en`, `es`, `fr`, `de`, `ja`, `zh`, `ru`, `ar`.
- Arquivos de tradução: `apps/web/messages/*.json`:
  `ar.json`, `de.json`, `en.json`, `es.json`, `fr.json`, `ja.json`, `pt-BR.json`, `ru.json`, `zh.json`.
- Carregamento: `apps/web/i18n/request.ts:5-13` importa `../messages/${locale}.json` e usa `defaultLocale=pt-BR`.
- Seletor de idioma: `apps/web/components/layout/language-switcher.tsx:12-27` lista os 9 idiomas e grava o cookie `NEXT_LOCALE` (`language-switcher.tsx:26`, `61`).
- Backend: locale existe apenas como preferência do usuário:
  - `UserSettingsModel.locale` em `modules/users/adapters/models.py:53`;
  - `UserSettingsResponse.locale` em `apps/api/routers/users.py:67`;
  - `UpdateSettingsInput.locale` em `users.py:130`;
  - `GET /api/v1/users/me/settings` e `PUT /api/v1/users/me/settings` em `users.py:325-353`.
- O frontend envia locale ao backend apenas ao salvar/consultar settings (`apps/web/stores/settings.ts:110-166`).

### 4.2 NÃO EXISTE

- **NÃO EXISTE** o conjunto de 11 locales. Existem 9; faltam 2 em relação ao requisito.
- **NÃO EXISTE** propagação do idioma atual para as requisições de geração/edição:
  - nenhum header `Accept-Language`/`X-Locale`;
  - nenhum parâmetro `locale` em `GenerateImageInput`/`EditImageInput` (`modules/image_generation/application/schemas.py:24-35`);
  - nenhum cookie `NEXT_LOCALE` lido pelo backend;
  - o CORS lista apenas `Authorization`, `Content-Type` e `X-Anonymous-Session` (`apps/api/main.py:114-120`); `Accept-Language` é safelisted, mas o backend não o lê.
- **NÃO EXISTE** mensagem de recusa traduzida: `SCOPE_REFUSAL_MESSAGE` é só PT (`shared_kernel/security_errors.py:10-14`).
- **NÃO EXISTE** system prompt do classificador em 11 idiomas: está só em PT (`prompt_classifier.py:23-36`).
- **NÃO EXISTE** reescrita/tradução de prompt no backend.

### 4.3 Cobertura de chaves

Comparação de chaves aninhadas contra `pt-BR.json`:

| Arquivo | Chaves | Faltando vs. pt-BR | Extra |
|---|---:|---:|---:|
| `pt-BR.json` | 288 | 0 | 0 |
| `en.json` | 288 | 0 | 0 |
| `ar.json` | 138 | 150 | 0 |
| `de.json` | 138 | 150 | 0 |
| `es.json` | 138 | 150 | 0 |
| `fr.json` | 138 | 150 | 0 |
| `ja.json` | 138 | 150 | 0 |
| `ru.json` | 138 | 150 | 0 |
| `zh.json` | 138 | 150 | 0 |

O README ainda afirma “i18n (en/pt-BR)” em `README.md:46`, o que não reflete nem os 9 locales atuais.

### 4.4 Riscos/inconsistências do item 4

- O idioma do site não influencia o prompt, a recusa, o classificador ou a futura reescrita. O LLM local não saberá o idioma do usuário a menos que o idioma seja incluído no texto ou em um header/parâmetro novo.
- O frontend descarta a mensagem de erro do backend e usa mensagens genéricas em `errors.generationHttp` (`apps/web/messages/pt-BR.json:188-189`), então a recusa fixa não é exibida no idioma do site.
- O cookie `NEXT_LOCALE` é gravado pelo frontend, mas o backend não o lê.
- O CORS não lista headers customizados de locale (ex.: `X-Locale`); se esse for o mecanismo escolhido, a lista de headers permitidos precisará ser alterada. `Accept-Language` é safelisted, mas não é lido pelo backend.
- As 7 traduções incompletas têm apenas 138 chaves; telas de conta/configurações e novas telas de geração provavelmente cairão em fallback ou mostrarão chaves cruas.

---

## 5. Fila, tempo real e limites

### 5.1 Celery/RabbitMQ

- App Celery: `workers/celery_app/celery.py:18-23`.
- Broker/backend: `settings.celery_broker_url` (RabbitMQ) e `settings.celery_result_backend` (Redis) em `infra/settings.py:47-50`.
- Filas: `generation.standard`, `generation.priority`, `generation.dlq` (`celery.py:37-41`).
- Rota da task: `process_generation_task` vai para `generation.standard` (`celery.py:42-44`).
- Timeouts: `task_time_limit=600`, `task_soft_time_limit=540` (`celery.py:32-33`).
- Retry: `worker_prefetch_multiplier=1`, `task_default_retry_delay=5` (`celery.py:34-35`).
- Task: `workers/celery_app/tasks.py:65-82`, com `autoretry_for=(ConnectionError, TimeoutError)`, `retry_backoff=True`, `retry_backoff_max=120`, `retry_jitter=True`, `max_retries=3`.
- DLQ: `_send_to_dlq` publica `dead_letter_task` na fila `generation.dlq` (`tasks.py:85-96`).
- Worker Docker: `CMD ["celery", "...", "worker", "--loglevel=info", "--queues=generation.standard,generation.priority"]` em `infra/docker/Dockerfile.worker:34`.
- **NÃO EXISTE** `--concurrency=1`, `--max-tasks-per-child`, limite de memória, fila dedicada a GPU ou worker separado para geração. O default do Celery é usar o número de CPUs (16 threads nesta máquina).
- **NÃO EXISTE** uso efetivo da fila `generation.priority`: `CeleryTaskQueue.enqueue_generation` aceita `priority=True` (`modules/image_generation/adapters/celery_task_queue.py:15-19`), mas os use cases chamam sem `priority` (`generate_image.py:72`, `edit_image.py:53`).

### 5.2 SSE

- Endpoint: `GET /api/v1/generations/{id}/stream` em `apps/api/routers/stream.py:43-104`.
- Transporte: Redis Pub/Sub, canal `stream_channel(generation_id)` (`stream.py:76-78`).
- Eventos mapeados por status (`stream.py:93-99`):
  - `queued` → `status_update`
  - `processing` → `progress`
  - `done` → `result`
  - `failed` → `error`
- Timeout máximo do stream: 600 s (`stream.py:37`); keepalive/ping a cada 15 s (`stream.py:38`, `85-90`).
- O worker publica:
  - `processing` 5 (`process_generation.py:53`);
  - `processing` 5+percent até 95 (`process_generation.py:55-56`);
  - `done` 100 com `result_image_url` (`process_generation.py:62`);
  - `failed` 100 com `error` (`process_generation.py:66`).
- **NÃO EXISTE** replay/estado inicial: o endpoint só se inscreve no Pub/Sub (`stream.py:76-78`) e não consulta o banco antes. Se o worker publicar `done`/`failed` antes do `EventSource` conectar, o evento é perdido e o cliente espera até 600 s.
- **NÃO EXISTE** evento `queued` publicado pelo worker; o status inicial não é enviado.
- O progresso é grosseiro: o `noop_progress` do orquestrador descarta os eventos do provider (`orchestrator.py:109-111`); na prática o SSE vê 5, 95 e 100.
- **Contrato quebrado:** o backend envia `progress` (`schemas.py:89`) e `result_image_url` (`schemas.py:90`); o frontend lê `payload.percent` (`generation.ts:108`) e `payload.imageUrl` (`generation.ts:114`). O progresso fica `undefined` e a imagem do resultado não é preenchida.

### 5.3 Limite de prompts (1/24h deslogado, 3/24h logado)

- Configuração: `anonymous_prompt_chances_per_day: int = 1` e `authenticated_prompt_chances_per_day: int = 3` em `infra/settings.py:81-85`.
- Store: `RedisPromptQuotaStore` em `modules/prompt_quota/adapters/redis_quota_store.py:70-113`.
- Janela deslizante de 24 h por chance, com sorted set e scripts Lua atômicos (`redis_quota_store.py:20-45`).
- Chaves: `prompt-quota:user:{id}` e `prompt-quota:anon:{id}` (`redis_quota_store.py:75-76`; `generations.py:65`, `78`).
- Consumo:
  - `POST /api/v1/generations` autenticado: `ConsumePromptQuota(store, total=3)` (`generations.py:64-65`);
  - anônimo: `ConsumePromptQuota(store, total=1)` (`generations.py:77-78`);
  - endpoint dedicado `POST /api/v1/prompt-quota/consume` também consome (`apps/api/routers/prompt_quota.py:63-82`), mas o frontend só usa `GET /api/v1/prompt-quota` (`apps/web/stores/prompt-quota.ts:42-51`).
- **Ela afeta recusas?** Sim. A cota é consumida no router **antes** de `GenerateImageFromPrompt`/`GenerateImageAnonymous`, que só então rodam `PromptInjectionGuard` e `PromptTopicGuard` (`generations.py:62-72`, `74-84`). Um prompt recusado por injeção ou escopo queima a chance.
- **Edições não passam pela cota diária:** `create_edit` só aplica o token bucket e o credito do usuário (`generations.py:103-112`).
- **Cota adicional de créditos:** `User.consume_credit()` em `modules/users/domain/entities.py:39-46`, chamado em `generate_image.py:59` e `edit_image.py:38`. O padrão é 50 créditos (`entities.py:9`, `24`); não há reset mensal implementado.

### 5.4 Rate limiting

- Middleware por IP: 120 req/min (`apps/api/middlewares/rate_limit.py:18-36`), exceto `/healthz`, `/readyz`, `/metrics`.
- Por usuário/anon na geração: `RATE_LIMIT_GENERATION_PER_MINUTE=10` (`settings.py:88-90`) e `TokenBucket` em `apps/api/dependencies.py:262-269`.
- Auth: 5/min (`settings.py:89`; `dependencies.py:268-269`).
- `TokenBucket` usa `time.monotonic()` como timestamp em Redis (`modules/rate_limiting/token_bucket.py:53-55`). Em múltiplas réplicas/hosts, relógios monotônicos não são sincronizados; o estado compartilhado pode ficar inconsistente. Não é o foco desta fase, mas é um risco de arquitetura distribuída.

### 5.5 Riscos/inconsistências do item 5

- Timeout de 600 s do Celery e do SSE é curto para FLUX em CPU (ver riscos de hardware).
- Sem `concurrency=1`, o worker pode tentar carregar/executar múltiplas difusões simultaneamente, estourando RAM/VRAM.
- Sem `--max-tasks-per-child`, vazamentos de memória do runtime de difusão se acumulam.
- Sem replay no SSE, resultados podem ser perdidos.
- Contratos SSE divergentes impedem o frontend de mostrar progresso e imagem.
- Cota consumida antes da validação é uma regra de negócio provavelmente indesejada.
- Edições fora da cota diária permitem uso acima do limite declarado.
- O `TokenBucket` baseado em `monotonic()` não é seguro para múltiplos hosts.

---

## 6. Armazenamento e banco

### 6.1 S3 / storage

- **NÃO EXISTE** integração S3 no projeto:
  - `pyproject.toml:20-46` não declara `boto3`, `aioboto3`, `s3fs` ou similar;
  - não há código de upload/download S3;
  - `STORAGE_BUCKET_URL` em `.env.example:78` é apenas uma URL base;
  - em `wiring.py:76-77`, ela é usada como base do `StubImageProvider` (fallback `https://picsum.photos`).
- **NÃO EXISTE** persistência de imagem gerada:
  - `HttpImageProvider` levanta erro ao receber `image_base64` porque “Storage proprio nao configurado” (`providers.py:88-92`);
  - se o provedor devolver `image_url`, a URL é apenas repassada e gravada em `generations.result_image_url` (`models.py:31`);
  - não há bucket, CDN, diretório público ou rota de serving de arquivos gerados.
- **NÃO EXISTE** upload de imagem de origem para edição:
  - `EditImageInput` exige `source_image_url: HttpUrl` (`schemas.py:34-35`);
  - `UrlPolicy` exige HTTPS e allowlist (`modules/image_generation/domain/url_policy.py:31-47`);
  - o frontend anexa a imagem como base64 (`studio-app.tsx:135`, `generation.ts:83`), mas o backend não aceita `image` no schema de geração e não há endpoint multipart de origem para edição.
- **NÃO EXISTE** uso do `SecureImageFetcher` no fluxo atual. Ele existe (`adapters/secure_image_fetcher.py:28-71`), mas não é construído no wiring nem chamado por use case.
- O upload de avatar tem um TODO explícito de S3 (`apps/api/routers/users.py:245`) e usa data URL em memória/base64 (`users.py:246-249`).

### 6.2 Tabelas e migrations

Tabelas reais:

| Tabela | Modelo | Migration | Observação |
|---|---|---|---|
| `users` | `modules/users/adapters/models.py:14-35` | `alembic/versions/0001_initial.py:20-34` + `0002` (`22-23`) + `20260918_161435` (`21-29`) | e-mail, nome, google_sub, password_hash, avatar_url, bio, handle, generation_credits |
| `generations` | `modules/image_generation/adapters/repositories/models.py:14-46` | `0001_initial.py:36-64` + `0002` (`26-36`) | prompt, negative_prompt, style_preset, aspect_ratio, source_image_url, result_image_url, status, kind, soft delete, anonymous_session_id |
| `user_settings` | `modules/users/adapters/models.py:38-83` | `20260918_161435_user_settings_and_profile.py:32-65` | preferências, locale, acessibilidade, notificações, privacidade |

- Galeria **não tem tabela própria**: é uma leitura de `generations` com `status='done'`, `result_image_url` não nulo, `user_id` não nulo e `deleted_at` nulo (`generation_repository.py:116-127`).
- `prompt_quota` **não usa Postgres**: é Redis (`prompt_quota/adapters/redis_quota_store.py`).
- **NÃO EXISTE** tabela/serviço de auditoria de tentativas bloqueadas. As migrations só criam/alteram `users`, `generations` e `user_settings`; não há tabela de logs, moderação ou recusas.
- **NÃO EXISTE** tabela de imagens geradas separada; os metadados ficam em `generations` e o binário não é persistido pelo backend.

### 6.3 Riscos/inconsistências do item 6

- Sem storage, um adapter FLUX local que devolva bytes/base64 não tem onde gravar; a URL de resultado precisa ser servida por algum componente (S3, MinIO, arquivo estático, CDN).
- Sem upload de origem, o fluxo de edição com Kontext não fecha: o frontend tem a imagem em base64, mas o backend só aceita URL allowlisted.
- O `SecureImageFetcher` não está integrado; a segunda linha de defesa anti-SSRF existe mas não é exercitada no fluxo real.
- A galeria pública depende de `result_image_url`; sem storage real, a galeria não terá imagens geradas.
- O avatar em data URL pode inflar o banco e não é compatível com o TODO de S3.

---

## 7. Observabilidade

### 7.1 Existe

- **Prometheus:** endpoint `GET /metrics` em `apps/api/routers/metrics.py:12-14`, usando `render_metrics()` (`modules/observability/metrics.py:51-52`).
- **Middleware HTTP:** `MetricsMiddleware` mede latência e conta requisições por método/endpoint/status (`apps/api/middlewares/metrics.py:13-23`).
- **Métricas definidas** em `modules/observability/metrics.py:7-48`:
  - `aimaginator_http_requests_total` (Counter);
  - `aimaginator_http_request_latency_seconds` (Histogram);
  - `aimaginator_generations_total` (Counter);
  - `aimaginator_generation_duration_seconds` (Histogram);
  - `aimaginator_cache_operations_total` (Counter);
  - `aimaginator_circuit_breaker_open` (Gauge);
  - `aimaginator_celery_queue_size` (Gauge);
  - `aimaginator_rate_limit_rejections_total` (Counter).
- **Prometheus config:** scrape `api:8000/metrics` a cada 15 s (`infra/docker/prometheus/prometheus.yml:1-12`).
- **Grafana:** datasource e dashboard provisionados (`infra/docker/grafana/provisioning/datasources/datasource.yml`, `.../dashboards/dashboards.yml`, `infra/docker/grafana/dashboards/api-health.json`).
- **Sentry backend:** `init_sentry` em `modules/observability/sentry_setup.py:36-50`, chamado no lifespan (`apps/api/main.py:83`). Faz scrubbing de headers/cookies/prompt (`sentry_setup.py:16-33`).
- **Logs estruturados:** `structlog` em `modules/observability/logging_config.py:10-29`.

### 7.2 NÃO EXISTE / não está ligado

- Apenas `HTTP_REQUESTS_TOTAL` e `HTTP_REQUEST_LATENCY` são incrementados (uso em `apps/api/middlewares/metrics.py:10-23`). As outras 6 métricas são definidas, mas **não são usadas em nenhum lugar**:
  - `GENERATIONS_TOTAL`, `GENERATION_DURATION`, `CACHE_OPERATIONS`, `CIRCUIT_BREAKER_STATE`, `CELERY_QUEUE_SIZE`, `RATE_LIMIT_REJECTIONS`.
- O dashboard do Grafana consulta `aimaginator_generation_duration_seconds_bucket`, `aimaginator_cache_operations_total`, `aimaginator_circuit_breaker_open` e `aimaginator_rate_limit_rejections_total` (ver `api-health.json`), que ficarão vazios.
- **Sentry frontend NÃO EXISTE:** `apps/web/instrumentation.ts:1-10` é apenas um comentário/placeholder; `@sentry/nextjs` não está em `apps/web/package.json`. `NEXT_PUBLIC_SENTRY_DSN` existe no `.env.example` mas não é usado.
- **Sentry backend está desligado no ambiente atual:** `SENTRY_DSN_BACKEND` está vazio no `.env`; `init_sentry` retorna sem inicializar (`sentry_setup.py:37-38`).
- **`PROMETHEUS_MULTIPROC_DIR`** está no `.env.example:66`, mas não é lido por `settings.py` nem usado; com múltiplos workers/processos as métricas não seriam agregadas.
- **NÃO EXISTE** métrica de negócio de recusas por escopo/moderação, fila por tipo, tempo de carregamento de modelo, VRAM/RAM ou erros de provider.
- **NÃO EXISTE** auditoria de tentativas bloqueadas (ver item 6).
- Prometheus local não está respondendo em `localhost:9090` durante a inspeção; Grafana responde em `localhost:3001` (provavelmente outra stack, ver item 9).

### 7.3 Riscos/inconsistências do item 7

- O painel Prometheus/Grafana dá a impressão de cobertura de geração, cache e circuit breaker, mas só as métricas HTTP são reais.
- Sem Sentry no frontend, erros de UI/SSE não são reportados.
- Sem `PROMETHEUS_MULTIPROC_DIR`, um deploy com múltiplos workers não agrega métricas corretamente.
- O scrub do Sentry remove `prompt` de headers/vars, mas não há garantia de que prompts não apareçam em mensagens de exceção; a política precisa ser revista ao integrar LLM local.

---

## 8. Frontend

### 8.1 Existe: tela de geração

- Rota do estúdio: `apps/web/app/[locale]/studio/page.tsx`.
- Componente principal: `apps/web/components/studio/studio-app.tsx`.
  - textarea de prompt (`studio-app.tsx:120-132`);
  - upload de imagem PNG/JPEG (`studio-app.tsx:135-141`);
  - preview da imagem anexada (`studio-app.tsx:143-166`);
  - botão de geração (`studio-app.tsx:169-184`);
  - progresso/resultado (`studio-app.tsx:187-225`);
  - histórico (`studio-app.tsx:227-253`).
- Landing: `apps/web/components/home/prompt-bar.tsx`; o submit redireciona para `/{locale}/studio?prompt=...` (`prompt-bar.tsx:62`).
- **Overlay “em breve” para usuário autenticado:** `studio-app.tsx:99-104` e `prompt-bar.tsx:180-185` mostram “A geração de imagens por IA ainda não está disponível” (`messages/pt-BR.json:66`). O overlay é `pointer-events-none` no studio (`studio-app.tsx:99-104`), então o formulário ainda pode ser usado por baixo, mas a UI comunica que a geração não existe.
- **Overlay de login para não autenticado:** `studio-app.tsx:79-97` e `prompt-bar.tsx:168-178`; o backend, porém, suporta geração anônima.

### 8.2 NÃO EXISTE: seletor de proporção

- **NÃO EXISTE** seletor de proporção no frontend.
- Busca por `aspect_ratio`, `AspectRatio`, `1:1`, `16:9`, `9:16`, `3:4` não encontrou nenhum controle de UI; só há:
  - classes CSS `aspect-*` em componentes de layout/galeria;
  - `aspectRatio` no `image-cropper.tsx` (`apps/web/components/ui/image-cropper.tsx:11`, `20`), usado para crop de avatar, não para geração.
- O frontend não envia `aspect_ratio`, `style_preset`, `negative_prompt` nem `title`; o backend usa os defaults `1:1` e `none` (`schemas.py:29-30`).

### 8.3 Existe: Galeria

- Página: `apps/web/app/[locale]/gallery/page.tsx`.
- Galeria pública: `apps/web/components/gallery/gallery-list.tsx`; store `apps/web/stores/gallery.ts`.
- Minha galeria: `apps/web/components/gallery/my-gallery.tsx`; store `apps/web/stores/my-gallery.ts`.
- A galeria pública consome `GET /api/v1/gallery/public` (`app/[locale]/gallery/page.tsx:20-30`) e usa `imageUrl` (`gallery-list.tsx:34-43`), que o backend serializa via alias `imageUrl` (`schemas.py:68-77`).
- A minha galeria consome `GET /api/v1/gallery/me`, `PATCH /api/v1/gallery/me/{id}` e `DELETE /api/v1/gallery/me/{id}` (`stores/my-gallery.ts:36-91`).

### 8.4 Existe: consumo de SSE e Zustand

- Store de geração: `apps/web/stores/generation.ts:53-144` (Zustand).
- Envio: `POST {API_BASE_URL}/api/v1/generations` com `{prompt, image}` (`generation.ts:80-84`).
- SSE: `EventSource` em `generation.ts:101-127`, com listeners `status_update`, `progress`, `result`, `error`.
- Stores adicionais:
  - `apps/web/stores/prompt-quota.ts` (cota);
  - `apps/web/stores/auth.ts` (auth);
  - `apps/web/stores/gallery.ts` (galeria pública);
  - `apps/web/stores/my-gallery.ts` (galeria pessoal);
  - `apps/web/stores/settings.ts` (preferências).
- **Contratos quebrados no frontend:**
  - envia `image` (`generation.ts:83`), mas `GenerateImageInput` não tem esse campo (`schemas.py:24-31`) e a edição exige `source_image_url` (`schemas.py:34-35`);
  - lê `payload.percent` (`generation.ts:108`), mas o backend envia `progress` (`schemas.py:89`);
  - lê `payload.imageUrl` (`generation.ts:114`), mas o backend envia `result_image_url` (`schemas.py:90`, `process_generation.py:62`);
  - lê `data.cursor` no histórico (`generation.ts:138-141`), mas o backend devolve `next_cursor` (`schemas.py:61-65`);
  - em erro HTTP, mostra `errors.http(status)` (`generation.ts:85-87`) em vez da mensagem do backend;
  - em erro SSE, lê `payload.message` (`generation.ts:121`), mas o backend envia `error` (`process_generation.py:66`).
- **NÃO EXISTE** proxy Next.js para SSE; o `EventSource` aponta direto para `API_BASE_URL` (`generation.ts:90-101`). O token de acesso vai na query string (`generation.ts:93-100`), o que pode vazar em logs/histórico.

### 8.5 Logo

- Arquivo: `apps/web/public/AImaginator_pic_transparent.png`.
- Dimensões medidas: **1412 x 1114 px**.
- Formato: PNG 32bpp ARGB; tamanho: **854.286 bytes (~834 KB)**.
- Uso: `apps/web/app/[locale]/page.tsx:99-103` com `width={1412}` e `height={1114}` (`page.tsx:101-102`).

### 8.6 Riscos/inconsistências do item 8

- A UI diz explicitamente que a geração não está disponível; isso precisa ser removido/alterado quando o FLUX entrar.
- O overlay de login impede o fluxo anônimo que o backend suporta.
- Não há seletor de proporção, estilo ou qualidade; o backend sempre recebe os defaults.
- O upload de imagem é apenas preview/base64 local; não é enviado como imagem de origem para edição.
- Os contratos de SSE/histórico/erro estão dessincronizados entre frontend e backend.
- O token JWT em query string é um risco de exposição.

---

## 9. Ambiente local do FLUX (inspeção, sem instalar nada)

### 9.1 Sistema

| Item | Resultado |
|---|---|
| SO | Microsoft Windows 11 Home, versão 10.0.26200, 64 bits |
| CPU | AMD Ryzen 7 5800X 8-Core (8 núcleos / 16 threads) |
| RAM total | 15,93 GB (16.701.480 KB) |
| RAM livre durante a inspeção | ~0,84 GB a ~1,49 GB (variou) |
| Pagefile | 24.576 MB alocados; 4.351 MB em uso |
| GPU | AMD Radeon RX 6500 XT (8 GB) |
| VRAM real dedicada | **~8 GB**: dxdiag `Dedicated Memory: 8146 MB`; Vulkan heap `DEVICE_LOCAL` = 8.573.157.376 bytes (7,98 GiB / 8.176 MiB) |
| VRAM no WMI | 4.293.918.720 bytes — **valor incorreto/truncado; NÃO usar** (`AdapterRAM` é campo de 32 bits) |
| Uso dedicado em idle | ~1,08–1,09 GB (`\GPU Adapter Memory(*)\Dedicated Usage`, LUID `...110f8...`) |
| Total comprometido em idle | ~1,30 GB (`\GPU Adapter Memory(*)\Total Committed`) |
| Driver Windows | 32.0.21025.15011, data 15/09/2025 |
| Driver AMD/Vulkan | AMD proprietary 25.9.2; Vulkan 1.4.315; deviceID 0x743f |
| CUDA/NVIDIA | NÃO EXISTE (`nvidia-smi` não encontrado) |
| Vulkan | `vulkaninfo` disponível; dispositivo discreto AMD reconhecido |
| Python do sistema | 3.14.0 |
| Python do `.venv` | 3.11.9 |
| `.python-version` | `3.12` (inconsistente com o `.venv` 3.11.9) |
| Faixa do `pyproject.toml` | `>=3.11,<=3.13` (`pyproject.toml:10`) |

### 9.1.1 Verificação real da VRAM (medição obrigatória)

O valor de ~4 GB lido de `Win32_VideoController.AdapterRAM` está errado para esta placa: esse campo é de 32 bits e satura em 4.293.918.720 bytes. As medições reais são:

- **Vulkan (`vulkaninfo --text`), GPU discreta AMD, heap com `MEMORY_HEAP_DEVICE_LOCAL_BIT`:**
  - `memoryHeaps[1].size = 8.573.157.376 bytes` (0x1FF000000) = **7,98 GiB / 8.176 MiB / 8,57 GB decimais**;
  - `memoryHeaps[1].budget = 7.736.627.200 bytes` = **7,21 GiB** no momento da medição;
  - `memoryHeaps[1].usage = 0` no momento da consulta;
  - flags: `MEMORY_HEAP_DEVICE_LOCAL_BIT | MEMORY_HEAP_MULTI_INSTANCE_BIT`;
  - o outro heap (`memoryHeaps[0]`, ~7,96 GiB, `flags: None`) é o heap não dedicado/compartilhado; não deve ser somado como VRAM.
- **dxdiag (relatório existente em `C:\Users\ALISSO~1\AppData\Local\Temp\kilo\dxdiag.txt`):**
  - `Card name: AMD Radeon RX 6500 XT`;
  - `Dedicated Memory: 8146 MB`;
  - `Shared Memory: 8155 MB`;
  - `Display Memory: 16301 MB` (dedicada + compartilhada).
- **Contadores de desempenho do Windows (`GPU Adapter Memory`), LUID da GPU discreta `luid_0x00000000_0x000110f8_phys_0`:**
  - `Dedicated Usage`: 1.165.725.696 a 1.158.893.568 bytes (~1,08–1,09 GB) em 5 amostras de 1 s, em idle;
  - `Total Committed`: ~1,40 GB em idle.
  - Esses contadores medem **uso**, não a capacidade total. Para pico de VRAM em testes, amostrar `Dedicated Usage` antes/durante/depois e registrar o máximo; o Gerenciador de Tarefas (Desempenho → GPU → “Memória de GPU dedicada”) usa a mesma fonte DXGI e serve como confirmação visual.
- **Conclusão da medição:** a VRAM dedicada real é **~8 GB (8.146 MB pelo dxdiag; 7,98 GiB pelo heap Vulkan)**, não 4 GB. O valor do WMI deve ser descartado.
- **Pico de VRAM:** não houve teste de carga do FLUX nesta fase (não há runtime de difusão instalado nem modelo Kontext/T5/CLIP/VAE); portanto, o pico não foi medido. O método para a próxima fase é amostrar `\GPU Adapter Memory(*)\Dedicated Usage` antes/durante/depois e registrar o máximo, confirmando no Gerenciador de Tarefas.

### 9.2 Ferramentas de difusão

- **ComfyUI:** NÃO EXISTE (não encontrado em `C:\`, `D:\`, `.lmstudio`, `Downloads`, `Documents`, `Desktop`; não há comando no PATH).
- **stable-diffusion.cpp:** NÃO EXISTE (não há binário/comando; não há diretório).
- **Forge / stable-diffusion-webui:** NÃO EXISTE.
- **diffusers/transformers/torch:** NÃO EXISTE no `.venv` do projeto nem no Python global 3.14 (busca por pacotes não retornou nada).
- O `.venv` do projeto tem apenas dependências mínimas de API/teste; não tem Celery, LangGraph, CrewAI, LangChain, Sentry SDK, boto3, torch ou diffusers. Os imports pesados são lazy, por isso os testes passam.
- O Python global 3.14 tem alguns pacotes de IA (langgraph 1.2.18, openai 3.42.0, boto3, celery 5.4.0), mas está fora da faixa suportada (`<=3.13`) e não é o ambiente do projeto.

### 9.3 Arquivos de modelo encontrados

Busca recursiva em `C:\Users\Alisson Davi\.lmstudio\models` e localizações prováveis (`.cache`, Downloads, Documents, Desktop, D:\):

| Arquivo | Caminho | Tamanho |
|---|---|---:|
| FLUX.1 Dev Q5_K_S | `C:\Users\Alisson Davi\.lmstudio\models\city96\FLUX.1-dev-gguf\flux1-dev-Q5_K_S.gguf` | 8.285.267.232 bytes (7,72 GiB) |
| Qwen3.5 9B Q4_K_M | `C:\Users\Alisson Davi\.lmstudio\models\lmstudio-community\Qwen3.5-9B-GGUF\Qwen3.5-9B-Q4_K_M.gguf` | 5.627.044.256 bytes (5,24 GiB) |
| Qwen3.5 9B mmproj BF16 | `C:\Users\Alisson Davi\.lmstudio\models\lmstudio-community\Qwen3.5-9B-GGUF\mmproj-Qwen3.5-9B-BF16.gguf` | 921.704.480 bytes (0,86 GiB) |

**NÃO EXISTE** FLUX Kontext nas localizações inspecionadas.
**NÃO EXISTE** T5 (ex.: `t5xxl_fp16.safetensors`/GGUF), CLIP (`clip_l.safetensors`), VAE (`ae.safetensors`) nas localizações inspecionadas.
**NÃO FOI ENCONTRADO** cache Hugging Face em `C:\Users\Alisson Davi\.cache\huggingface` nem `AppData\Local\huggingface`.

Observação: a busca foi feita nas localizações acima, não em uma varredura exaustiva de todos os arquivos do disco; não foram encontrados diretórios de modelos além do `.lmstudio\models`, `.ollama\models` e `.docker\models`.

### 9.4 LM Studio

- Endpoint `http://localhost:1235/v1/models`: **HTTP 200**.
- Modelos listados:
  - `flux.1-dev` (publisher `city96`, arch `flux`, GGUF, Q5_K_S, `state: not-loaded`);
  - `qwen/qwen3.5-9b` (VLM, Q4_K_M, `state: not-loaded`);
  - `text-embedding-nomic-embed-text-v1.5` (embeddings, `state: not-loaded`).
- Endpoint `http://localhost:1235/api/v0/models`: confirma **todos `not-loaded`**.
- Porta `1234`: conexão recusada; o servidor está em **1235**.
- Log recente do LM Studio mostra Qwen3.5-9B carregado às 08:56 e descarregado por TTL às 10:19; não há registro de carregamento do FLUX.
- O LM Studio tem backends llama.cpp Vulkan/CUDA/AVX2, mas não há evidência de runtime de difusão configurado para o FLUX.

### 9.5 Docker/portas locais

- `docker ps` mostra uma stack de outro projeto (`forja-*`): `forja-postgres` (pgvector/pg16), `forja-redis`, `forja-rabbitmq`, `forja-backend`, `forja-otel-collector`, além de `docker-rabbitmq-1` unhealthy.
- Portas ocupadas: 5432 (Postgres), 6379 (Redis), 5672/15672 (RabbitMQ), 3000 (Grafana) e 8000 (wslrelay, provavelmente backend da outra stack).
- `localhost:8000/healthz` retornou **404**, não o health check do AImaginator; a API do AImaginator não está rodando.
- `localhost:9090` (Prometheus) não estava acessível; `localhost:3001` estava acessível (provavelmente Grafana/outra stack).
- Subir o `docker-compose` do AImaginator como está vai conflitar com essas portas.

### 9.6 Riscos/inconsistências do item 9

- O `.env` de produção e a stack de outro projeto ocupando portas tornam o ambiente atual impróprio para desenvolvimento local.
- O LM Studio não está com modelo carregado; o FLUX não foi testado.
- Não há runtime de difusão instalado; o GGUF do FLUX sozinho não é suficiente (faltam T5/CLIP/VAE e um executor).
- 8 GB de VRAM e ~16 GB de RAM ainda são apertados para FLUX + Kontext + LLM local simultâneos; FLUX Q5 fica no limite da VRAM e Kontext exige quantização.

---

## 10. Documentação e testes

### 10.1 `docs/agent/RULES.md` e `PROGRESS.md`

- **NÃO EXISTIA** o diretório `docs/` antes desta entrega; ele foi criado apenas para este relatório.
- **NÃO EXISTE** `docs/agent/RULES.md`.
- **NÃO EXISTE** `docs/agent/PROGRESS.md`.
- Portanto, não há “regras do agente” nem progresso formal nesses arquivos para resumir.

Regras que existem de fato, em outros lugares:

- **Clean Architecture por módulo:** cada módulo expõe apenas `contracts.py`; nenhum módulo importa `domain/`/`adapters/` de outro (`README.md:61-96`).
- **Configuração centralizada:** só `infra/settings.py` lê ambiente; nenhum outro arquivo deve chamar `os.getenv` (`infra/settings.py:1-9`, `README.md:247-249`).
- **Geração nunca síncrona:** Celery + RabbitMQ; SSE via Redis Pub/Sub (`README.md:37-39`, `100-110`, ADR-003 em `README.md:243-245`).
- **Segurança:** PromptInjectionGuard, UrlPolicy anti-SSRF, payload limit, rate limiting, sem stack trace ao cliente (`README.md:190-206`; `apps/api/main.py:132-156`).
- **TDD + EDD:** pytest + evals de agentes (`README.md:148-165`; `specs/evals/README.md`).
- **Context Engineering:** carregar apenas o subgrafo do módulo + shared_kernel + contratos, nunca o projeto inteiro (`context_graph/README.md:5-20`).
- **Specs por caso de uso:** `specs/image_generation/generate_image_from_prompt.spec.md` e `specs/image_generation/edit_image_from_prompt.spec.md`.

### 10.2 Testes executados

Comandos executados com `.venv\Scripts\python.exe` e `npm` em `apps/web`:

| Suíte | Comando | Resultado |
|---|---|---|
| Backend total | `pytest tests` | **1 failed, 122 passed, 1 skipped** em ~12-14 s |
| Guardrail de tópico | `pytest tests/unit/test_prompt_topic_guard.py` | **11 passed** |
| Guardrail de injeção | `pytest tests/unit/test_prompt_guard.py` | **21 passed, 1 failed** |
| Cota de prompts | `pytest tests/unit/test_prompt_quota.py` | **6 passed** |
| Integração API | `pytest tests/integration/test_api.py` | **18 passed** |
| Evals de agentes | `pytest specs/evals -m eval` | **4 passed** |
| Frontend unit (vitest) | `npm run test -- --run` | **13 passed (6 arquivos)** |
| Frontend e2e (Playwright) | `npm run test:e2e` | **5 passed** |

Detalhes:

- O skip é `tests/integration/test_no_n_plus_1.py:58`: “Requer Postgres real (CI usa service container; defina RUN_DB_TESTS=1)”.
- A falha é o teste property-based `test_property_prompts_benignos_nunca_sao_rejeitados` (`tests/unit/test_prompt_guard.py:75-80`), com o caso gerado `JAILBREAK`, rejeitado pelo padrão `r"jailbreak"` (`prompt_guard.py:33`).
- Nenhum teste foi corrigido ou alterado.
- A suíte de backend não cobre worker Celery, provider HTTP real, classificador HTTP/Gemini real, SSE com Redis real, quota consumida antes da validação, nem o fluxo de edição ponta a ponta.

### 10.3 Riscos/inconsistências do item 10

- A ausência de `docs/agent/RULES.md`/`PROGRESS.md` significa que não há contrato formal de regras/progresso para esta integração; as regras estão espalhadas em README/specs/context_graph.
- O README está desatualizado em i18n (diz en/pt-BR, mas há 9 locales) e em provedor de imagem (stub/HTTP genérico).
- A suíte não está verde; a falha é de teste, não de código, mas precisa ser resolvida antes de um gate de CI.
- O CI em `infra/github/workflows/ci.yml` não está em `.github/workflows/`, então o GitHub Actions não o executa automaticamente. **NÃO EXISTE** `.github/` no repositório.

---

## 11. LACUNAS (o que falta para integrar FLUX + Kontext + LLM local)

1. **Adapter real de geração FLUX:** implementar um `ImageProvider` local (stable-diffusion.cpp, ComfyUI, diffusers ou LM Studio, se suportar difusão) atrás da porta existente; carregar modelo/VAE/T5/CLIP; configurar resolução, steps, guidance, seed, sampler e negative prompt.
2. **Adapter real de edição Kontext:** criar uma porta/implementação de edição (não existe `ImageEditor`); obter o modelo Kontext e os auxiliares; receber a imagem de origem (upload/base64/URL), pré-processar e devolver a imagem editada.
3. **Storage de imagens:** S3/MinIO/local com URL pública/assinada; persistir bytes e metadados; adaptar `HttpImageProvider`/novo provider para não levantar erro com base64; servir a imagem para galeria/SSE.
4. **Upload de imagem de origem:** endpoint multipart ou base64 para edição; validação de tipo/tamanho; integração com `SecureImageFetcher`; política de retenção/LGPD.
5. **LLM local no backend:** configuração `LM_STUDIO_BASE_URL`/modelo/chave; cliente OpenAI-compatível reutilizável; usar para escopo, moderação e reescrita/tradução; fallback e timeouts; testes com mock HTTP.
6. **Moderação de conteúdo:** camada separada do `PromptInjectionGuard` (NSFW, violência, legal, PII), com política de recusa e mensagem fixa; decidir se bloqueia antes ou depois do classificador de escopo.
7. **Reescrita/tradução em 11 idiomas:** prompt de sistema multilíngue; detecção/entrada do locale; saída no idioma do usuário; testes por idioma; mensagens de recusa traduzidas.
8. **i18n completo:** adicionar os 2 locales faltantes e as 150 chaves ausentes nos 7 locales incompletos; propagar locale via header/parâmetro/cookie; se usar header customizado (ex.: `X-Locale`), permitir no CORS; `Accept-Language` não precisa de allowlist, mas precisa ser lido pelo backend.
9. **Contratos frontend/backend:** alinhar `image`/`source_image_url`, `percent`/`progress`, `imageUrl`/`result_image_url`, `cursor`/`next_cursor`; exibir mensagens de erro do backend; remover overlays “em breve”; implementar seletor de proporção/estilo/qualidade.
10. **SSE resiliente:** enviar estado inicial do banco ao conectar; replay/último evento; progresso real do provider; timeout compatível com difusão local; teste com Redis real.
11. **Fila adequada a GPU/CPU:** `concurrency=1`, `max-tasks-per-child`, timeouts maiores, fila dedicada, carregamento persistente do modelo, limites de memória/VRAM e DLQ.
12. **Cota/limites:** decidir se recusas consomem cota; aplicar cota também em edições; unificar créditos e cota diária; testar a ordem quota → validação.
13. **Auditoria:** tabela/serviço de tentativas bloqueadas (principal, locale, camada, motivo, confiança, timestamp, hash do prompt), com retenção e LGPD.
14. **Observabilidade:** instrumentar métricas de geração/cache/circuit breaker/fila/rate limit; Sentry no frontend; Sentry backend ativo; métricas de modelo (tempo de carga, RAM/VRAM, falhas).
15. **Ambiente local:** separar `.env.development` do `.env` de produção; subir Postgres/Redis/RabbitMQ sem conflito com a stack ForjaB2B; rodar API/worker/frontend localmente; documentar.
16. **Documentação:** criar `docs/agent/RULES.md` e `PROGRESS.md`; atualizar README (i18n, provider, estado real); registrar decisões de arquitetura do FLUX/Kontext.

---

## 12. RISCOS DE HARDWARE (estimativa de caber ou não)

### 12.1 Resumo

- **GPU:** AMD Radeon RX 6500 XT, **~8 GB de VRAM dedicada** (dxdiag 8146 MB; heap Vulkan `DEVICE_LOCAL` 7,98 GiB), sem CUDA. É uma GPU de entrada, com Vulkan; não há ROCm/CUDA instalado. A VRAM é o principal gargalo.
- **RAM:** **15,93 GB totais**, com **~0,8–1,5 GB livres** durante a inspeção. Mesmo fechando aplicativos, o teto é ~16 GB.
- **CPU:** Ryzen 7 5800X (8C/16T), bom para offload, mas lento para difusão em 1024x1024.
- **Disco:** C: ~115 GB livres; D: ~18,9 GB livres. Há espaço para alguns modelos, não para muitos checkpoints em paralelo.

### 12.2 FLUX.1 Dev Q5_K_S (geração)

- Peso do arquivo: **7,72 GiB** (7.901 MiB).
- **VRAM dedicada real:** **8.176 MiB** (heap Vulkan) / 8.146 MB (dxdiag).
- **Cabeçalho de VRAM:** 8.176 − 7.901 = **~275 MiB livres** para contexto Vulkan, ativações, buffers de imagem e runtime. Isso é muito pouco; o Q5 provavelmente **não cabe inteiro** na GPU com overhead.
- **Regra de teste:** não usar offload total. Testar primeiro o modelo de difusão na GPU e deixar **T5, CLIP e, se necessário, o VAE na CPU**.
- **RAM para T5 na CPU:** T5 fp8 ~4,9 GiB ou fp16 ~9,5 GiB; CLIP ~0,25 GiB; VAE ~0,17 GiB. Com 16 GB totais e ~1,5 GB livres, é preciso fechar aplicativos e/ou quantizar o T5. O peso do FLUX fica na VRAM, mas o runtime ainda usa RAM para buffers/host.
- **Estimativa:**
  - Q5 inteiro na GPU → **muito apertado/não confiável** (só ~275 MiB de folga);
  - Q4/Q3 na GPU + T5/CLIP/VAE na CPU → **viável com monitoramento**, começando em 512–768 px e 8–12 steps;
  - Q5 com offload total → **não recomendado** (contraria a orientação e tende a ficar lento);
  - FLUX + Qwen carregado junto → **NÃO**.

### 12.3 FLUX Kontext (edição)

- Modelo não está presente; estimativas típicas para FLUX.1 Kontext dev (11,9B parâmetros):
  - BF16: **~23,8 GB**;
  - FP8: **~11,9 GB**;
  - GGUF Q5: **~8–9 GB**;
  - GGUF Q4: **~7 GB**.
- Além do Kontext, precisa de T5/CLIP/VAE e da imagem de entrada.
- **VRAM de 8 GB:** Q4 (~7 GB) pode caber com ~1 GB de folga, mas é apertado; Q5 (~8–9 GB) provavelmente não cabe; BF16/FP8 não cabe.
- **RAM:** com Kontext Q4 na GPU e T5 fp8 na CPU, o consumo de RAM fica em torno de **5–7 GiB** para T5 + runtime, ainda dependendo do espaço livre real.
- **Estimativa:** “Q4 na GPU + T5/CLIP/VAE na CPU” → **talvez, no limite**; “Q5 na GPU” → **improvável**; “BF16/FP8” → **NÃO**.

### 12.4 LLM local (Qwen3.5 9B Q4_K_M)

- Peso: **5,24 GiB** + mmproj **0,86 GiB**.
- **VRAM de 8 GB:** cabe sozinho com ~2 GB de folga; pode rodar na GPU.
- **RAM:** ~6 GiB; cabe sozinho em 16 GB, mas **não junto com FLUX/Kontext** na mesma GPU.
- O LM Studio já carregou esse modelo com contexto 16384 e o descarregou por TTL; isso confirma que ele roda, mas não que roda simultaneamente com difusão.
- **Estimativa:** sozinho na GPU → **cabe**; junto com FLUX na GPU → **NÃO cabe**; simultâneo com FLUX (LLM na CPU) → possível, mas disputa RAM e CPU.

### 12.5 Tempo e limites de task

- Com o modelo de difusão na GPU e T5 na CPU, o tempo deve cair bastante em relação a CPU pura, mas o encode do T5 e o runtime Vulkan ainda precisam ser medidos. Não há medição de FLUX nesta fase.
- O Celery tem `task_time_limit=600` e `task_soft_time_limit=540` (`celery.py:32-33`); o SSE tem `_MAX_STREAM_SECONDS=600` (`stream.py:37`).
- **Risco** de a task ser morta e/ou o SSE expirar antes do resultado, especialmente se o Q5 não couber e for necessário offload parcial. Para desenvolvimento, aumentar os limites e usar resolução menor (512–768) e menos steps.
- O worker sem `concurrency=1` pode tentar duas difusões ao mesmo tempo e estourar a VRAM/RAM.

### 12.6 Recomendações de hardware (sem implementar)

- Medir o pico de VRAM com `\GPU Adapter Memory(*)\Dedicated Usage` (LUID da GPU discreta) e confirmar no Gerenciador de Tarefas; **nunca** usar `AdapterRAM` do WMI.
- Testar primeiro o modelo de difusão na GPU, com T5/CLIP/VAE na CPU; se o Q5 não couber, usar Q4/Q3 em vez de partir para offload total.
- Começar em 512x512 ou 768x768, 8–12 steps; só depois tentar 1024x1024.
- Usar T5/CLIP/VAE quantizados (fp8/Q4) e manter apenas um modelo de difusão carregado por vez.
- Rodar o LLM local e o FLUX **sequencialmente**, não simultaneamente; ou usar um LLM bem menor (ex.: 3B/4B) para escopo/reescrita.
- Para Kontext, priorizar Q4; Q5/BF16/FP8 não cabem confortavelmente em 8 GB. Considerar execução remota/API se a qualidade exigir o modelo completo.
- Aumentar timeouts de Celery/SSE e definir `concurrency=1` antes de testar FLUX local.
- Monitorar RAM/VRAM e tempo por geração; sem essas métricas, não há como provar viabilidade.

---

## 13. Sugestão de divisão em fases curtas (sem implementar nada)

### Fase 1 — Spike de runtime local (1–2 dias)

- Escolher o runtime: stable-diffusion.cpp Vulkan, ComfyUI ou diffusers (ou confirmar LM Studio).
- Rodar FLUX Q5_K_S em 512x512, 8–12 steps, mantendo o modelo de difusão na GPU e T5/CLIP/VAE na CPU; se o Q5 não couber, testar Q4/Q3 antes de considerar offload total.
- Medir tempo, RAM pico, VRAM pico (contadores `GPU Adapter Memory` + Gerenciador de Tarefas) e qualidade.
- Entregável: relatório de viabilidade e comando reproduzível; nenhum código de produto.

### Fase 2 — Porta/adapters de imagem (2–3 dias)

- Definir a porta de edição (ou reutilizar `ImageProvider` com contrato explícito para `kind=edit`).
- Implementar `LocalFluxImageProvider` e `LocalKontextImageEditor` atrás das portas.
- Implementar storage (S3/MinIO/local) e serving de URL.
- Testes com runtime fake (sem carregar modelo) + um teste manual.

### Fase 3 — LLM local (2–3 dias)

- Adicionar settings `LM_STUDIO_*` e cliente OpenAI-compatível reutilizável.
- Migrar o classificador de escopo para LM Studio (mantendo Gemini/HTTP como fallback).
- Adicionar moderação e reescrita/tradução; testes por idioma.
- Definir prompts de sistema multilíngues e política de recusa.

### Fase 4 — Fluxo de edição (2–3 dias)

- Upload de imagem de origem (multipart/base64) + validação/tamanho.
- Integrar `SecureImageFetcher` ou storage local.
- Ligar Kontext ao `kind=edit`; alinhar `source_image_url`/`image`.
- Testes de edição ponta a ponta.

### Fase 5 — Contratos, SSE e frontend (2–3 dias)

- Alinhar payloads (`progress`, `result_image_url`, `next_cursor`, erros).
- Enviar estado inicial no SSE e progresso real.
- Remover overlays “em breve”; adicionar seletor de proporção/estilo.
- Exibir mensagens de recusa do backend.

### Fase 6 — i18n e limites (2 dias)

- Adicionar 2 locales e as 150 chaves faltantes.
- Propagar locale do frontend ao backend.
- Traduzir mensagens de recusa/classificador.
- Decidir e implementar a ordem cota → validação; aplicar cota em edições.

### Fase 7 — Operação e auditoria (2 dias)

- `concurrency=1`, timeouts maiores, fila dedicada, limites de memória.
- Métricas reais de geração/fila/VRAM/RAM; Sentry backend/frontend.
- Tabela/serviço de auditoria de recusas.
- Separar `.env.development` do `.env` de produção; resolver conflito de portas com a stack ForjaB2B.

### Fase 8 — E2E, carga e segurança (2 dias)

- Testes E2E de geração/edição com runtime real.
- Testes de carga (fila, SSE, concorrência), segurança (injection multilíngue, SSRF, cota).
- Documentar `docs/agent/RULES.md` e `PROGRESS.md`, atualizar README.

---

## 14. Anexo — evidências de comandos

- `git status --porcelain`: vazio antes deste relatório; branch `main`, commit `9066aa5`.
- `pytest tests`: `1 failed, 122 passed, 1 skipped`.
- `pytest tests/unit/test_prompt_topic_guard.py`: `11 passed`.
- `pytest tests/unit/test_prompt_quota.py`: `6 passed`.
- `pytest tests/unit/test_prompt_guard.py`: `21 passed, 1 failed`.
- `pytest tests/integration/test_api.py`: `18 passed`.
- `pytest specs/evals -m eval`: `4 passed`.
- `npm run test -- --run`: `6 files, 13 tests passed`.
- `npm run test:e2e`: `5 passed`.
- `GET http://localhost:1235/v1/models`: HTTP 200; 3 modelos; todos `not-loaded` via `/api/v0/models`.
- `nvidia-smi`: não encontrado.
- `vulkaninfo --summary`: AMD Radeon RX 6500 XT, driver AMD proprietary 25.9.2, Vulkan 1.4.315.
- `Get-CimInstance Win32_OperatingSystem`: Windows 11 Home 10.0.26200; 15,93 GB totais; 0,84–1,49 GB livres.
- `Get-CimInstance Win32_VideoController`: AMD Radeon RX 6500 XT; `AdapterRAM` = 4.293.918.720 bytes — **valor de 32 bits, incorreto; não usar**; driver 32.0.21025.15011.
- `vulkaninfo --text`: heap `MEMORY_HEAP_DEVICE_LOCAL_BIT` = 8.573.157.376 bytes (7,98 GiB / 8.176 MiB); budget = 7.736.627.200 bytes (7,21 GiB).
- `dxdiag`: `Dedicated Memory: 8146 MB`; `Shared Memory: 8155 MB`; `Display Memory: 16301 MB`.
- `Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage'`: ~1,08–1,09 GB em idle (5 amostras de 1 s, LUID `...110f8...`); `Total Committed` ~1,30 GB. Esses contadores medem uso, não capacidade.
- VRAM dedicada real: **~8 GB**, não 4 GB.
- `Get-ChildItem .lmstudio\models -Recurse`: apenas FLUX Q5_K_S, Qwen3.5 9B Q4_K_M e mmproj; nenhum Kontext/T5/CLIP/VAE.
- `docker ps`: stack `forja-*` ocupando portas 5432/6379/5672/15672; `localhost:8000` retorna 404; API do AImaginator não está rodando.
- `docs/agent/RULES.md` e `docs/agent/PROGRESS.md`: **NÃO EXISTEM**.

---

**Conclusão:** o esqueleto de API, fila, SSE, guardrails e testes existe e é razoável, mas a geração/edição real, o storage, o LLM local de moderação/reescrita, o i18n de 11 idiomas e a compatibilidade de hardware ainda não existem. A VRAM dedicada real é **~8 GB** (não 4 GB); mesmo assim, FLUX Q5 fica no limite (só ~275 MiB de folga) e Kontext exige Q4/quantização. O maior bloqueio imediato é a combinação 8 GB VRAM + 16 GB RAM para FLUX + Kontext + LLM local; o segundo é a ausência de runtime/adapters e de storage para os resultados.
