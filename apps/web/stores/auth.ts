import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";
import {clearSession, getAccessToken} from "@/lib/auth-token";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  avatarUrl: string | null;
};

type AuthStatus = "unknown" | "loading" | "authenticated" | "unauthenticated";

type AuthState = {
  user: AuthUser | null;
  status: AuthStatus;
  fetchMe: () => Promise<void>;
  logout: () => void;
  loginUrl: string;
};

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
        const user = (await res.json()) as AuthUser;
        set({user, status: "authenticated"});
        return;
      }
      set({user: null, status: "unauthenticated"});
    } catch {
      set({user: null, status: "unauthenticated"});
    }
  },

  logout() {
    clearSession();
    set({user: null, status: "unauthenticated"});
  },
}));
