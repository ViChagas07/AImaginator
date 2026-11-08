# Validação manual com modelos reais

Execute **uma etapa por vez**, feche programas pesados e monitore RAM,
temperatura e energia. O PC de desenvolvimento já desligou sob carga longa do
Kontext. Nenhum script abaixo é executado pelo CI.

## Antes de começar

1. Use `.env.development` (não o `.env` de produção).
2. Confirme `FEATURE_IMAGE_GENERATION_ENABLED=true`.
3. Baixe os pesos e configure os caminhos `SDCPP_*`, `LLM_*`,
   `IMAGE_NSFW_MODEL_PATH`/`IMAGE_CLIP_MODEL_PATH` e `S3_*`.
4. Suba a infraestrutura de desenvolvimento:

```bash
docker compose --env-file .env.development -f infra/docker/docker-compose.yml up -d postgres redis rabbitmq minio
```

## Ordem recomendada

### 1. Geração FLUX

```bash
python tools/smoke_sdcpp.py
```

Acompanhe o tempo, a RAM e a temperatura. Saída esperada:
`smoke-output.png` (512×512, 8 steps).

### 2. Edição Kontext

```bash
python tools/smoke_sdcpp.py --edit --source caminho/entrada.png
```

A edição tem timeout próprio de 10 minutos. Interrompa ao primeiro sinal de
throttle, ruído anormal ou queda.

### 3. Assistente local

Com o LM Studio carregado:

```bash
python tools/smoke_assistant.py
```

O script mostra latência da primeira chamada e das seguintes, decisão,
`flux_prompt`/`kontext_instruction`, recusas e casos limítrofes.

### 4. Moderação de imagem

```bash
python tools/smoke_moderation.py --folder C:/imagens-do-usuario
```

O usuário fornece as imagens; o script não gera nem baixa nada. Ajuste
`IMAGE_NSFW_THRESHOLD`, `IMAGE_GORE_THRESHOLD`, `IMAGE_HATE_THRESHOLD` e
`IMAGE_SELF_HARM_THRESHOLD` com base nos scores.

### 5. Evals reais e relatório

```bash
python tools/run_evals_report.py
```

Gera `docs/agent/EVALS_REPORT.md` com acurácia por categoria/idioma, falsos
bloqueios/passes e latência. Use para calibrar `LLM_BLOCK_CONFIDENCE`.

### 6. Fluxo completo pela interface

Suba API, worker, frontend e MinIO; abra `/{locale}/studio` e valide:
geração, edição por upload, refino, variação, upscale, download, histórico,
recusas localizadas e o aviso “em breve” com a flag desligada.

## E2E de infraestrutura (sem modelos reais)

Com a infraestrutura local no ar e o worker usando o executável falso:

```bash
RUN_E2E_INFRA=1 E2E_API_URL=http://localhost:8001 E2E_ACCESS_TOKEN=... pytest tests/integration/test_e2e_infra.py -s
```

Sem `RUN_E2E_INFRA=1` o teste é pulado.

## Notas das Fases 7.5/7.6

- Confirme `LLM_REASONING_EFFORT=none` e, se quiser liberar RAM antes do FLUX,
  `LLM_UNLOAD_AFTER_USE=true` com `LMS_CLI_PATH` valido (ou `lms` no PATH).
- Se o modelo responder truncado, o cliente tenta uma vez com
  `LLM_MAX_OUTPUT_TOKENS_RETRY`; se persistir, o job falha de forma segura.
- Para geracoes antigas sem original, refino/upscale retornam
  `original_unavailable`; regenere a imagem antes de testar.
- O reconciliador de fila roda no startup do worker e ao abrir
  stream/historico; `QUEUE_STALE_SECONDS` controla a idade considerada perda.

Caminhos opcionais de moderacao no E2E (quando o worker estiver com o fake
configurado para bloquear):

```bash
E2E_TEXT_MODERATION=1 E2E_TEXT_MODERATION_PROMPT="..." \
E2E_IMAGE_MODERATION=1 E2E_BLOCKED_IMAGE=C:/caminho/bloqueada.png \
RUN_E2E_INFRA=1 E2E_API_URL=http://localhost:8001 E2E_ACCESS_TOKEN=... \
pytest tests/integration/test_e2e_infra.py -s
```

O bloqueio de texto chega como `content_blocked_*` no SSE; o de imagem de
origem chega como `source_image_blocked_*`.
