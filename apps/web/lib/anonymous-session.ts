const ANON_KEY = "aimaginator.anonymous_session";

export function getAnonymousToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ANON_KEY);
}

export function saveAnonymousToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ANON_KEY, token);
}

export function clearAnonymousToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ANON_KEY);
}
