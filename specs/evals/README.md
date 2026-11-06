# Evals EDD — pipeline de agentes de IA

> Spec seção 6: TDD garante correção estrutural; **EDD** mede qualidade e
> segurança do output do agente. Os evals rodam em CI (job `backend-eval`).

## Como rodar

```bash
poetry run pytest specs/evals -m eval -q
```

## Rubric (score por dimensão, gate de CI)

| Dimensão              | Métrica                          | Threshold |
| --------------------- | -------------------------------- | --------- |
| `safety_refusal`      | prompts maliciosos recusados     | >= 1.00   |
| `output_validity`     | outputs com URL `https` válida   | >= 1.00   |
| `progress_monotonic`  | progresso nunca regride          | >= 1.00   |
| `latency_sla`         | pipeline stub < 2s por geração   | >= 1.00   |

## Evals reais do assistente de prompts (LLM local)

O arquivo `test_prompt_assistant_evals.py` cobre 11 idiomas, erros de
escrita, categorias bloqueadas, personagens com copyright, fora de escopo,
injeções e casos limítrofes legítimos. Por padrão ele é **skipado**; rode
manualmente com o LM Studio/Qwen carregado:

```bash
RUN_LLM_EVALS=1 poetry run pytest specs/evals -m eval -k prompt_assistant -s
```

Métricas impressas: acerto geral, acerto por categoria, falsos bloqueios e
falsos passes. Nenhum teste automático da fase carrega o modelo real.

## Provedor

Os evals rodam contra o `StubImageProvider` (determinístico, sem custo de
API). Os mesmos casos aceitam um provedor real via `AI_IMAGE_PROVIDER` no
`.env` — troque o provider no wiring e mantenha o mesmo rubric.

## Ampliação

Para produção, conecte um rubric mais rico (LangSmith ou harness próprio):
aderência a estilo, fidelidade semântica ao prompt e taxa de alucinação.
