# AImaginator — Web

Frontend do AImaginator: Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui (convenção `@/components/ui`) + Zustand + next-intl (en/pt-BR) + lucide-react.

## Setup

```bash
npm install
cp .env.local.example .env.local  # ajuste NEXT_PUBLIC_API_BASE_URL
npm run dev
```

Backend: FastAPI em `http://localhost:8000` (`/api/v1/...`). Auth via Google OAuth2/OIDC com cookies httpOnly — o login é apenas um link para `/api/v1/auth/google/login`; chamadas do cliente passam por Route Handlers (`app/api/*`).

## Scripts

- `npm run dev` — servidor de desenvolvimento
- `npm run build` / `npm start` — build de produção
- `npm run lint` — ESLint
- `npm test` — vitest + Testing Library + axe (a11y)
- `npm run test:e2e` — Playwright (porta dedicada 3110, chromium já instalado via `npx playwright install chromium`)

## Sentry

O SDK não foi instalado. Para ativar, rode o wizard (sobrescreve `instrumentation.ts` e instala `@sentry/nextjs`):

```bash
npx @sentry/wizard@latest -i nextjs --saas --org paysentineliq --project aimaginator
```
