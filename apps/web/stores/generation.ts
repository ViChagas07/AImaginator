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

export type GenerationErrorMessages = {
  http: (status: number) => string;
  failed: string;
  network: string;
};

type GenerationState = {
  prompt: string;
  imageBase64: string | undefined;
  status: GenerationStatus;
  progress: number;
  resultUrl: string | null;
  error: string | null;
  history: HistoryItem[];
  historyCursor: string | null;
  startGeneration: (
    prompt: string,
    imageBase64: string | undefined,
    errors: GenerationErrorMessages,
  ) => Promise<void>;
  loadHistory: () => Promise<void>;
  reset: () => void;
  setPrompt: (p: string) => void;
  setImage: (image: string | undefined) => void;
};

export function isGeneratingStatus(status: GenerationStatus): boolean {
  return status === "queued" || status === "processing";
}

let source: EventSource | null = null;

export const useGenerationStore = create<GenerationState>((set, get) => ({
  prompt: "",
  imageBase64: undefined,
  status: "idle",
  progress: 0,
  resultUrl: null,
  error: null,
  history: [],
  historyCursor: null,

  setPrompt: (prompt) => set({prompt}),

  setImage: (imageBase64) => set({imageBase64}),

  reset: () => {
    source?.close();
    source = null;
    set({prompt: "", imageBase64: undefined, status: "idle", progress: 0, resultUrl: null, error: null});
  },

  async startGeneration(prompt, imageBase64, errors) {
    source?.close();
    set({prompt, status: "queued", progress: 0, resultUrl: null, error: null});
    try {
      const res = await fetch("/api/generations", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({prompt, image: imageBase64 ?? null}),
      });
      if (!res.ok) {
        set({status: "failed", error: errors.http(res.status)});
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
        let message = errors.failed;
        try {
          const payload = JSON.parse((event as MessageEvent).data) as {message?: string};
          if (payload.message) message = payload.message;
        } catch {
          // evento nativo de rede do EventSource — manter mensagem padrão
        }
        set({status: "failed", error: message});
      });
    } catch {
      set({status: "failed", error: errors.network});
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
