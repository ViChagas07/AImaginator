// Stub somente para testes: remove dependência do runtime do Next.js no vitest.

export function useRouter() {
  return {
    push: () => undefined,
    replace: () => undefined,
    refresh: () => undefined,
    back: () => undefined,
    forward: () => undefined,
    prefetch: () => undefined,
  };
}

export function usePathname() {
  return "/pt-BR";
}

export function useSearchParams() {
  return new URLSearchParams();
}

export function useParams() {
  return {};
}

export function redirect(): never {
  throw new Error("redirect is not available in tests");
}

export function notFound(): never {
  throw new Error("notFound is not available in tests");
}
