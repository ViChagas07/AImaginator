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

- `pip-audit --local`: **0 vulnerabilidades conhecidas** após upgrades.
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
