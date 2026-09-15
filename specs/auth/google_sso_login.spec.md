# Spec: GoogleSSOLogin

> Status: implementado · Módulo: `modules/auth`

## Intenção

Como usuário, quero entrar no AImaginator com minha conta Google via
OAuth 2.0 + OpenID Connect (Authorization Code + PKCE), sem criar senha local.

## Pré-condições

- Credenciais Google configuradas (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).
- Redis disponível (armazena `state` + `code_verifier` com TTL).

## Fluxo

1. `GET /api/v1/auth/google/login` → gera `state` + `code_verifier` (PKCE),
   persiste no Redis (TTL 10 min) e redireciona (302) para o Google.
2. Google redireciona para `/api/v1/auth/google/callback?code=..&state=..`.
3. Backend valida `state` (anti-CSRF), troca o code por tokens e valida o
   `id_token` contra o JWKS do Google (assinatura, `iss`, `aud`, `exp`).
4. Provisiona o usuário (upsert por `google_sub`) e emite a **sessão própria**
   (JWT HS256) gravada em cookies `httpOnly; Secure; SameSite=Lax`.
5. Redireciona para o frontend autenticado.

## Regras de negócio / segurança

- **Nenhum token do Google sai do backend** — só os JWTs da aplicação.
- `state` e `code_verifier` nunca ficam em cookie legível (anti-CSRF).
- Access token de curta duração + refresh token; `/refresh` reemite o access.
- Brute force mitigado por rate limit dedicado nos endpoints de auth.

## Casos de erro

| Cenário                        | Código HTTP | Motivo                    |
| ------------------------------ | ----------- | ------------------------- |
| `state` inválido/expirado      | 401         | anti-CSRF                 |
| `id_token` assinatura inválida | 401         | `unauthorized`            |
| Rate limit de auth             | 429         | `rate_limit_exceeded`     |

## Testes (TDD) obrigatórios

- [x] `JWTService`: roundtrip access, refresh não vale como access,
      token adulterado/expirado/chave errada rejeitados.
- [x] API `/auth/me` sem token → 401.

## Implementação

- `modules/auth/application/pkce.py` (RFC 7636)
- `modules/auth/application/oidc_service.py`
- `modules/auth/application/jwt_service.py`
- `modules/auth/application/use_cases.py`
- `apps/api/routers/auth.py`
