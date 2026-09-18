import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";

export type UserSettings = {
  user_id: string;
  // Aparência
  theme: "dark" | "light" | "system";
  bold_text: boolean;
  font_size: "small" | "medium" | "large" | "xl";
  element_spacing: "compact" | "comfortable" | "spacious";
  // Idioma e Região
  locale: string;
  timezone: string;
  // Acessibilidade
  high_contrast: boolean;
  screen_reader_optimized: boolean;
  keyboard_navigation: boolean;
  focus_indicator: boolean;
  dyslexia_font: boolean;
  reduced_motion: boolean;
  // Notificações
  email_notifications: boolean;
  push_notifications: boolean;
  desktop_notifications: boolean;
  sound_notifications: boolean;
  summary_frequency: "daily" | "weekly" | "never";
  notification_email: string | null;
  // Privacidade
  privacy_policy_version: string | null;
  terms_version: string | null;
  consented_at: string | null;
  // Avançado
  developer_mode: boolean;
  created_at: string;
  updated_at: string;
};

type SettingsState = {
  settings: UserSettings | null;
  draft: UserSettings | null;
  loading: boolean;
  saving: boolean;
  dirty: boolean;
  error: string | null;
  fetchSettings: () => Promise<void>;
  patchDraft: (data: Partial<UserSettings>) => void;
  saveDraft: () => Promise<void>;
  resetDraft: () => Promise<void>;
  applySettings: (settings: UserSettings) => void;
};

const DEFAULT_SETTINGS: UserSettings = {
  user_id: "",
  theme: "system",
  bold_text: false,
  font_size: "medium",
  element_spacing: "comfortable",
  locale: "pt-BR",
  timezone: "America/Sao_Paulo",
  high_contrast: false,
  screen_reader_optimized: false,
  keyboard_navigation: false,
  focus_indicator: false,
  dyslexia_font: false,
  reduced_motion: false,
  email_notifications: true,
  push_notifications: true,
  desktop_notifications: true,
  sound_notifications: true,
  summary_frequency: "weekly",
  notification_email: null,
  privacy_policy_version: null,
  terms_version: null,
  consented_at: null,
  developer_mode: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

function applyCSSVariables(settings: UserSettings) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  // Theme
  root.setAttribute("data-theme", settings.theme);
  // Font size
  const fontSizeMap = {small: "0.875rem", medium: "1rem", large: "1.125rem", xl: "1.25rem"};
  root.style.setProperty("--font-size-base", fontSizeMap[settings.font_size]);
  // Element spacing
  const spacingMap = {compact: "0.5rem", comfortable: "1rem", spacious: "1.5rem"};
  root.style.setProperty("--spacing-unit", spacingMap[settings.element_spacing]);
  // Bold text
  root.style.setProperty("--font-weight-base", settings.bold_text ? "600" : "400");
  // Accessibility classes
  root.classList.toggle("high-contrast", settings.high_contrast);
  root.classList.toggle("screen-reader-optimized", settings.screen_reader_optimized);
  root.classList.toggle("focus-visible-enhanced", settings.focus_indicator);
  root.classList.toggle("dyslexia-font", settings.dyslexia_font);
  root.classList.toggle("reduced-motion", settings.reduced_motion);
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: null,
  draft: null,
  loading: false,
  saving: false,
  dirty: false,
  error: null,

  async fetchSettings() {
    if (get().loading) return;
    set({loading: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/settings`, {cache: "no-store"});
      if (res.ok) {
        const data = (await res.json()) as Partial<UserSettings>;
        const settings = {...DEFAULT_SETTINGS, ...data, user_id: data.user_id ?? ""};
        applyCSSVariables(settings);
        set({settings, draft: settings, dirty: false});
      } else {
        set({error: "Erro ao carregar configurações"});
      }
    } catch {
      set({error: "Erro de rede ao carregar configurações"});
    } finally {
      set({loading: false});
    }
  },

  patchDraft(data) {
    const {draft} = get();
    if (!draft) return;
    const next = {...draft, ...data};
    applyCSSVariables(next);
    set({draft: next, dirty: true});
  },

  async saveDraft() {
    const {draft} = get();
    if (!draft) return;
    set({saving: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/settings`, {
        method: "PUT",
        headers: {"content-type": "application/json"},
        body: JSON.stringify(draft),
        cache: "no-store",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({detail: "Erro ao salvar"}));
        throw new Error(err.detail || "Erro ao salvar configurações");
      }
      set({settings: draft, dirty: false});
    } catch (e) {
      set({error: e instanceof Error ? e.message : "Erro ao salvar"});
      throw e;
    } finally {
      set({saving: false});
    }
  },

  async resetDraft() {
    set({saving: true, error: null});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/users/me/settings`, {
        method: "PUT",
        headers: {"content-type": "application/json"},
        body: JSON.stringify(DEFAULT_SETTINGS),
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Erro ao redefinir");
      const reset = {...DEFAULT_SETTINGS, user_id: get().draft?.user_id ?? ""};
      applyCSSVariables(reset);
      set({settings: reset, draft: reset, dirty: false});
    } catch (e) {
      set({error: e instanceof Error ? e.message : "Erro ao redefinir"});
      throw e;
    } finally {
      set({saving: false});
    }
  },

  applySettings: (settings) => {
    applyCSSVariables(settings);
  },
}));