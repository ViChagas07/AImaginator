# Compose prod-like

O compose de `infra/docker/docker-compose.yml` sobe Postgres, Redis, RabbitMQ,
MinIO, API e worker. Para um ensaio prod-like:

```bash
cp .env.development.example .env.development
# ajuste senhas/segredos e FEATURE_IMAGE_GENERATION_ENABLED=false inicialmente
docker compose --env-file .env.development -f infra/docker/docker-compose.yml up --build
```

Perfil de observabilidade com Alertmanager:

```bash
docker compose --env-file .env.development -f infra/docker/docker-compose.yml \
  --profile observability up
```

Checklist antes de expor:

- `APP_ENV=production`, `FEATURE_IMAGE_GENERATION_ENABLED=false` ate validar.
- TLS em broker/Redis/Postgres/S3; `ALLOW_REMOTE_INFRA_IN_DEV` nao se aplica.
- Worker remoto conforme `REMOTE_WORKER.md`, com credenciais proprias.
- Backups do Postgres/MinIO e retencao de `sources/`.
- Alertmanager apontando para um webhook real.
