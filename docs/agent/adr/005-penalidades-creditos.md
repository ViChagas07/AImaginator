# ADR-005 — Penalidades e devolução de créditos

## Status
Aceito.

## Decisão
Tentativas bloqueadas por moderação contam na janela de 24h: 3 = aviso,
5 = bloqueio de 1h, 10 = revisão + bloqueio de 24h. Escopo/injeção não contam.
Créditos e chance diária são devolvidos em recusa do LLM, falha do motor e
moderação (idempotente por geração); a penalidade continua valendo.

## Consequências
- Abuso não é incentivado pela devolução, pois o bloqueio permanece.
- Eventos de imagem de saída entram em `moderation_events` sem contar nível.
