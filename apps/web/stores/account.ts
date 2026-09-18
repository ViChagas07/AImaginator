import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";

export type AccountStats = {
  accountCreatedAt: string;
  totalGenerations: number;
  totalSavedArts: number;
  currentTier: string;
  creditsUsedThisPeriod: number;
  creditsLimit: number;
};

export type ConnectedProvider = {
  name: string;
  connected: boolean;
  email: string | null;
};

type AccountState = {
  stats: AccountStats | null;
  providers: ConnectedProvider[];
  loading: boolean;
  error: string | null;
  fetchStats: () => Promise<void>;
  fetchProviders: () => Promise<void>;
  uploadAvatar: (file: File) => Promise<string>;
  removeAvatar: () => Promise<void>;
  updateProfile: (data: {name?: string; bio?: string; handle?: string}) => Promise<void>;
};

export const useAccountStore = create<AccountState>((set) => ({
  stats: null,
  providers: [],
  loading: false,
  error: null,

  async fetchStats() {
    set({loading: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/stats`, {cache: "no-store"});
      if (res.ok) {
        const data = (await res.json()) as {
          account_created_at: string;
          total_generations: number;
          total_saved_arts: number;
          current_tier: string;
          credits_used_this_period: number;
          credits_limit: number;
        };
        set({
          stats: {
            accountCreatedAt: data.account_created_at,
            totalGenerations: data.total_generations,
            totalSavedArts: data.total_saved_arts,
            currentTier: data.current_tier,
            creditsUsedThisPeriod: data.credits_used_this_period,
            creditsLimit: data.credits_limit,
          },
        });
      } else {
        set({error: "Erro ao carregar estatísticas"});
      }
    } catch {
      set({error: "Erro de rede ao carregar estatísticas"});
    } finally {
      set({loading: false});
    }
  },

  async fetchProviders() {
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/providers`, {cache: "no-store"});
      if (res.ok) {
        const data = await res.json();
        set({providers: data.providers});
      }
    } catch {
      // silencioso
    }
  },

  async uploadAvatar(file) {
    set({loading: true, error: null});
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/avatar`, {
        method: "POST",
        body: formData,
        cache: "no-store",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({detail: "Erro no upload"}));
        throw new Error(err.detail || "Erro no upload");
      }
      const data = await res.json();
      return data.avatar_url;
    } finally {
      set({loading: false});
    }
  },

  async removeAvatar() {
    set({loading: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/avatar`, {
        method: "DELETE",
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Erro ao remover avatar");
    } finally {
      set({loading: false});
    }
  },

  async updateProfile(data) {
    set({loading: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me`, {
        method: "PUT",
        headers: {"content-type": "application/json"},
        body: JSON.stringify(data),
        cache: "no-store",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({detail: "Erro ao atualizar"}));
        throw new Error(err.detail || "Erro ao atualizar perfil");
      }
    } finally {
      set({loading: false});
    }
  },
}));