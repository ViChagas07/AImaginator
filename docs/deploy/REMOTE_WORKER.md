# Worker remoto (GPU em casa)

Topologia: API/frontend na nuvem, worker em uma maquina com GPU, conectado ao
Postgres, Redis, broker e S3 da nuvem. Nenhum modelo roda na API.

## Requisitos de seguranca

- `WORKER_MODE=remote` explicito.
- Broker `amqps://`, Redis `rediss://` e Postgres com `sslmode=require`.
- S3 por HTTPS; nunca bucket publico.
- Túnel/VPN (WireGuard/Tailscale) ou private endpoints; nao exponha GPU à
  internet.
- Credenciais distintas do worker (menor privilegio), nunca as mesmas da API.

## SQL de menor privilegio (exemplo)

```sql
CREATE ROLE aimaginator_worker LOGIN PASSWORD '<rotacione>';
GRANT CONNECT ON DATABASE aimaginator TO aimaginator_worker;
GRANT USAGE ON SCHEMA public TO aimaginator_worker;
GRANT SELECT, INSERT, UPDATE ON generations, users, credit_ledger TO aimaginator_worker;
GRANT SELECT ON moderation_events, admin_audit_log TO aimaginator_worker;
-- sem DELETE em users; sem DDL; sem superuser
```

## IAM S3 (exemplo, ajuste bucket/prefixos)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
     "Resource": [
       "arn:aws:s3:::SEU_BUCKET/generations/*",
       "arn:aws:s3:::SEU_BUCKET/sources/*",
       "arn:aws:s3:::SEU_BUCKET/avatars/*"
     ]}
  ]
}
```

## Broker

- Usuario do worker com permissao apenas nas filas `generation.standard` e
  `generation.dlq` (configure/consume).
- TLS obrigatorio; vhost dedicado; sem permissao de management.

## Execucao

```bash
export WORKER_MODE=remote
export CELERY_BROKER_URL=amqps://...
export REDIS_URL=rediss://...
export DATABASE_URL='postgresql+asyncpg://.../aimaginator?sslmode=require'
export S3_ENDPOINT_URL=https://...
poetry run celery -A workers.celery_app.celery:celery_app worker \
  --queues=generation.standard --pool=solo
```

O heartbeat do worker publica capacidades/estado; a API só aceita geracao se
houver worker vivo para o kind. O fallback `IMAGE_ENGINE_FALLBACK=hosted` pode
ser usado quando o worker local estiver offline.
