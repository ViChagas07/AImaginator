import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";
import {getAnonymousToken, saveAnonymousToken} from "@/lib/anonymous-session";

export type PromptQuotaState = {
  loaded: boolean;
  loading: boolean;
  chancesRemaining: number;
  chancesTotal: number;
  nextAvailableAt: string | null;
  authenticated: boolean;
  fetch: () => Promise<void>;
  refresh: () => Promise<void>;
};

type PromptQuotaResponse = {
  chances_remaining: number;
  chances_total: number;
  next_available_at: string | null;
  authenticated: boolean;
  anonymous_token: string | null;
};

function anonymousHeaders(): Headers {
  const headers = new Headers();
  const token = getAnonymousToken();
  if (token) headers.set("X-Anonymous-Session", token);
  return headers;
}

export const usePromptQuotaStore = create<PromptQuotaState>((set, get) => ({
  loaded: false,
  loading: false,
  chancesRemaining: 0,
  chancesTotal: 1,
  nextAvailableAt: null,
  authenticated: false,

  async fetch() {
    if (get().loading) return;
    set({loading: true});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/prompt-quota`, {
        headers: anonymousHeaders(),
        cache: "no-store",
      });
      if (!res.ok) return;
      const data = (await res.json()) as PromptQuotaResponse;
      if (data.anonymous_token) saveAnonymousToken(data.anonymous_token);
      set({
        loaded: true,
        chancesRemaining: data.chances_remaining,
        chancesTotal: data.chances_total,
        nextAvailableAt: data.next_available_at,
        authenticated: data.authenticated,
      });
    } catch {
      // rede/API indisponível — mantém o estado atual (sem blur indevido)
    } finally {
      set({loading: false});
    }
  },

  refresh: () => get().fetch(),
}));
