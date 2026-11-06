# ADR-004 — Feature flag de geração em produção

## Status
Aceito.

## Contexto
O site publicado não deve gerar imagens até o host/modelo estar validado.

## Decisão
`FEATURE_IMAGE_GENERATION_ENABLED` é derivado do ambiente (false em produção,
true em desenvolvimento) e configurável. Endpoints de geração/edição/variação/
upscale devolvem `feature_disabled` (503) quando desligado; `/config` informa o
frontend. Validações de sdcpp/S3/LLM só rodam com a flag ligada.

## Consequências
- Produção sobe sem modelos configurados, mostrando “em breve”.
- Para ligar, configure todos os paths, S3, LLM e defina a flag true.
