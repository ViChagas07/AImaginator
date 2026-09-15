# Spec: EditImageFromPrompt

> Status: implementado · Módulo: `modules/image_generation`

## Intenção

Como usuário autenticado, quero enviar a URL de uma imagem existente e pedir
uma edição (estilo, remoção/adição de elementos, etc.) via prompt.

## Pré-condições

- Usuário autenticado com cota disponível.
- A URL de origem pertence à allowlist de domínios (anti-SSRF).

## Contrato de entrada (porta)

`POST /api/v1/generations/edits` — `EditImageInput` (herda `GenerateImageInput`)

| Campo               | Tipo     | Regras                          |
| ------------------- | -------- | ------------------------------- |
| `source_image_url`  | `HttpUrl`| HTTPS + allowlist (anti-SSRF)   |
| `prompt`            | `str`    | sanitizado anti-injection       |

## Contrato de saída (porta)

`202 Accepted` — `GenerationOutput` (id, status, stream_url), como em
`GenerateImageFromPrompt`.

## Regras de negócio

- A URL passa pela `UrlPolicy` (domain): apenas HTTPS, domínio na allowlist,
  literais de IP e hosts internos recusados — **antes** de qualquer fetch.
- Segunda linha de defesa no `SecureImageFetcher` (adapter): resolução de DNS
  validada (bloqueia IP privado/loopback/link-local), sem seguir redirects e
  limite de 10 MB (anti buffer overflow).
- A edição é enfileirada no Celery (nunca síncrona).

## Casos de erro

| Cenário                            | Código HTTP | Motivo                       |
| ---------------------------------- | ----------- | ---------------------------- |
| URL fora da allowlist/sem HTTPS    | 422         | `url_not_allowed` (anti-SSRF)|
| URL aponta para host interno       | 422         | `url_not_allowed`            |
| Prompt malicioso                   | 422         | `prompt_rejected`            |
| Cota excedida                      | 429         | `quota_exceeded`             |

## Testes (TDD) obrigatórios

- [x] `UrlPolicy` bloqueia: HTTP, localhost, IP literal, metadata cloud,
      suffix spoofing, IP público fora da allowlist.
- [x] `UrlPolicy` permite domínios e subdomínios da allowlist.
- [x] API retorna 422 para edição com URL fora da allowlist.

## Implementação

- `modules/image_generation/application/use_cases/edit_image.py`
- `modules/image_generation/domain/url_policy.py`
- `modules/image_generation/adapters/secure_image_fetcher.py`
- `apps/api/routers/generations.py` (`POST /generations/edits`)
