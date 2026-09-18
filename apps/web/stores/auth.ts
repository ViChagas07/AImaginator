import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";
import {
  clearSession,
  getAccessToken,
  saveSession,
  type SessionTokens,
} from "@/lib/auth-token";
import {clearAnonymousToken, getAnonymousToken} from "@/lib/anonymous-session";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  avatarUrl: string | null;
  googleSub: string | null;
  bio: string | null;
  handle: string | null;
};

type AuthStatus = "unknown" | "loading" | "authenticated" | "unauthenticated";

export class AuthError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type AuthState = {
  user: AuthUser | null;
  status: AuthStatus;
  fetchMe: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  completeAuth: (tokens: SessionTokens) => Promise<void>;
  logout: () => void;
  loginUrl: string;
};

function setSession(tokens: SessionTokens) {
  saveSession(tokens);
}

async function claimAnonymousArts(): Promise<void> {
  const anon = getAnonymousToken();
  if (!anon) return;
  try {
    const headers = new Headers();
    headers.set("X-Anonymous-Session", anon);
    await authedFetch(`${API_BASE_URL}/api/v1/gallery/me/claim`, {
      method: "POST",
      headers,
      cache: "no-store",
    });
    clearAnonymousToken();
  } catch {
    // falha na migração não deve bloquear o login
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "unknown",
  loginUrl: `${API_BASE_URL}/api/v1/auth/google/login`,

  async fetchMe() {
    set({status: "loading"});
    if (!getAccessToken()) {
      set({user: null, status: "unauthenticated"});
      return;
    }
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/auth/me`, {
        cache: "no-store",
      });
      if (res.ok) {
        const data = (await res.json()) as {
          id: string;
          name: string;
          email: string;
          avatar_url: string | null;
          google_sub: string | null;
          bio: string | null;
          handle: string | null;
        };
        const user: AuthUser = {
          id: data.id,
          name: data.name,
          email: data.email,
          avatarUrl: data.avatar_url ?? null,
          googleSub: data.google_sub ?? null,
          bio: data.bio ?? null,
          handle: data.handle ?? null,
        };
        set({user, status: "authenticated"});
        return;
      }
      set({user: null, status: "unauthenticated"});
    } catch {
      set({user: null, status: "unauthenticated"});
    }
  },

  async signIn(email, password) {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({email, password}),
      cache: "no-store",
    });
    if (!res.ok) throw new AuthError(res.status, "invalid-credentials");
    const data = (await res.json()) as {
      access_token: string;
      refresh_token: string;
      user: AuthUser;
    };
    setSession({access_token: data.access_token, refresh_token: data.refresh_token});
    set({user: data.user, status: "authenticated"});
    await claimAnonymousArts();
  },

  async signUp(name, email, password) {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({name, email, password}),
      cache: "no-store",
    });
    if (!res.ok) {
      const status = res.status;
      if (status === 409) throw new AuthError(status, "email-in-use");
      throw new AuthError(status, "signup-failed");
    }
    const data = (await res.json()) as {
      access_token: string;
      refresh_token: string;
      user: AuthUser;
    };
    setSession({access_token: data.access_token, refresh_token: data.refresh_token});
    set({user: data.user, status: "authenticated"});
    await claimAnonymousArts();
  },

  async completeAuth(tokens) {
    setSession(tokens);
    set({status: "loading"});
    await claimAnonymousArts();
    await useAuthStore.getState().fetchMe();
  },

  logout() {
    clearSession();
    set({user: null, status: "unauthenticated"});
  },
}));
