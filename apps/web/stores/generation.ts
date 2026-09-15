import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";

export type GenerationStatus =
  | "idle"
  | "queued"
  | "processing"
  | "done"
  | "failed";

export type HistoryItem = {
  id: string;
  prompt: string;
  imageUrl: string | null;
  createdAt: string;
};

type GenerationState = {
  prompt: string;
  status: GenerationStatus;
  progress: number;
  resultUrl: string | null;
  error: string | null;
  history: HistoryItem[];
  historyCursor: string | null;
  startGeneration: (prompt: string, imageBase64?: string) => Promise<void>;
  loadHistory: () => Promise<void>;
  reset: () => void;
  setPrompt: (p: string) => void;
};

let source: EventSource | null = null;

export const useGenerationStore = create<GenerationState>((set, get) => ({
  prompt: "",
  status: "idle",
  progress: 0,
  resultUrl: null,
  error: null,
  history: [],
  historyCursor: null,

  setPrompt: (prompt) => set({prompt}),

  reset: () => {
    source?.close();
    source = null;
    set({prompt: "", status: "idle", progress: 0, resultUrl: null, error: null});
  },

  async startGeneration(prompt, imageBase64) {
    source?.close();
    set({prompt, status: "queued", progress: 0, resultUrl: null, error: null});
    try {
      const res = await fetch("/api/generations", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({prompt, image: imageBase64 ?? null}),
      });
      if (!res.ok) {
        const message = `Erro ${res.status}: não foi possível iniciar a geração. Tente novamente.`;
        set({status: "failed", error: message});
        return;
      }
      const data = (await res.json()) as {id: string; stream_url: string};
      const url = data.stream_url.startsWith("http")
        ? data.stream_url
        : `${API_BASE_URL}${data.stream_url}`;
      source = new EventSource(url, {withCredentials: true});
      source.addEventListener("status_update", (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as {status: GenerationStatus};
        set({status: payload.status});
      });
      source.addEventListener("progress", (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as {percent: number};
        set({status: "processing", progress: payload.percent});
      });
      source.addEventListener("result", (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as {imageUrl: string};
        source?.close();
        source = null;
        set({status: "done", progress: 100, resultUrl: payload.imageUrl});
      });
      source.addEventListener("error", (event) => {
        source?.close();
        source = null;
        let message = "A geração falhou. Tente novamente.";
        try {
          const payload = JSON.parse((event as MessageEvent).data) as {message?: string};
          if (payload.message) message = payload.message;
        } catch {
          // evento nativo de rede do EventSource — manter mensagem padrão
        }
        set({status: "failed", error: message});
      });
    } catch {
      set({status: "failed", error: "Falha de rede ao contatar a API. Verifique sua conexão e tente novamente."});
    }
  },

  async loadHistory() {
    const cursor = get().historyCursor;
    const params = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const res = await fetch(`/api/generations${params}`);
    if (!res.ok) return;
    const data = (await res.json()) as {items: HistoryItem[]; cursor: string | null};
    set({
      history: [...get().history, ...data.items],
      historyCursor: data.cursor,
    });
  },
}));
