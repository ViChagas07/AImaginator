# ADR-002 — LLM local no worker, antes do motor

## Status
Aceito.

## Contexto
O assistente precisa entender 11 idiomas, moderar e reescrever prompts sem
competir por RAM/VRAM com o FLUX.

## Decisão
O `PromptAssistant` chama o LM Studio (OpenAI-compatible) no worker, com
concorrência 1, antes de iniciar o subprocesso do motor. Saída JSON, uma
tentativa de reparo e fail-closed. O prompt original é preservado; apenas a
reescrita vai ao FLUX/Kontext.

## Consequências
- Testes usam `FakeLlmClient`; nenhuma chamada real em CI.
- `LLM_TTL_SECONDS` descarrega o modelo antes do motor quando o servidor aceita.
- Timeouts de task/SSE cobrem LLM + motor.
