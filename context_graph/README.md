# Context Graph — GraphiFy (Context Engineering)

> Spec seção 5: cada spec fechada vira nós/arestas no GraphiFy, dando ao
> agente um mapa de contexto navegável por módulo — em vez de reler o
> repositório inteiro a cada prompt.

## Regra prática

Carregar no contexto **apenas**:

1. o subgrafo do módulo sendo alterado;
2. o `shared_kernel`;
3. os contratos públicos (`contracts.py`) dos módulos consumidos.

Nunca o projeto inteiro.

## Artefato

- [`graph.json`](./graph.json) — grafo de contexto (módulos → casos de uso →
  portas/entidades → arquivos), atualizado a cada fase fechada.

## Convenção de arestas

| Aresta             | Significado                                            |
| ------------------ | ------------------------------------------------------ |
| `depends_on`       | caso de uso depende de uma porta/entidade/módulo       |
| `implemented_by`   | porta implementada por um adapter/arquivo concreto     |
| `uses`             | módulo consome o contrato público de outro módulo      |

## Como manter atualizado

Ao fechar uma fase: adicione/atualize o nó do caso de uso e suas arestas no
`graph.json`. Em ferramentas visuais (GraphiFy), o arquivo é importado como
subgrafo navegável.
