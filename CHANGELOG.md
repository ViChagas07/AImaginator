# Changelog

Formato: Conventional Commits. Datas em UTC.

## Unreleased

### Added
- Heartbeat de workers, disponibilidade por kind, endpoint `/api/v1/status` e
  modo `WORKER_MODE=remote`.
- Motor `hosted` (esqueleto HTTP) com fallback ordenado.
- Guarda termica/RAM com sensores fake/LibreHardwareMonitor e exporter manual.
- Ledger de creditos com planos, reset mensal e endpoint de uso.
- Console admin com auditoria, manutencao e ajuste de creditos.
- C2PA opcional no grupo `provenance`, tools de certificado/verificacao.
- Backfill de originais e avatar no S3 via proxy.
- Dependabot, CodeQL, gitleaks, gates de auditoria e build Docker.

### Changed
- FastAPI/Starlette/LangGraph atualizados; `crewai`/`langchain` removidos.
- Logs de assistente sem conteudo de prompt por padrao.
- Seed de creditos/planos usa ledger transacional.

### Fixed
- Fila orfa, publish que falhava sem refund e reasoning consumindo tokens.
- Categoria de moderacao derivada dos booleanos e reescrita sem enfeites.
