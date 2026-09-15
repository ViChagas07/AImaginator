// Sentry será inicializado pelo usuário via wizard interativo:
//  npx @sentry/wizard@latest -i nextjs --saas --org paysentineliq --project aimaginator
// O wizard sobrescreve este arquivo com Sentry.init usando
// process.env.NEXT_PUBLIC_SENTRY_DSN.
//
// import * as Sentry from "@sentry/nextjs";
//
// export async function register() {
//   if (process.env.NEXT_RUNTIME === "nodejs") {
//     Sentry.init({
//       dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
//       // Adjust the trace sample rate in production.
//       tracesSampleRate: 1,
//     });
//   }
// }
