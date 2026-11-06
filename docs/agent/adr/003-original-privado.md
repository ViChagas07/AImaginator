# ADR-003 — Original privado e versão pública com marca

## Status
Aceito.

## Contexto
Refino/upscale precisam do sinal limpo, mas o produto só deve servir a imagem
com marca d'água e metadados de IA.

## Decisão
Gravar `generations/{id}/original.png` (privado) antes da marca/metadados e
`generations/{id}/result.png` (público). URLs assinadas e respostas só usam o
resultado; refino e upscale leem o original.

## Consequências
- Gerações antigas sem original falham com `original_unavailable` (409).
- Backfill/regeração é necessário para refinar/ampliar imagens antigas.
