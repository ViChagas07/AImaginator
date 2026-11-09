import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";
import {getAccessToken} from "@/lib/auth-token";
import {getAnonymousToken, saveAnonymousToken} from "@/lib/anonymous-session";
import {
  buildEditImageUploadForm,
  ApiGenerationItem,
  GenerationRecord,
  parseGenerationOutput,
  readApiError,
  readErrorMessage,
  readNextCursor,
  readParentGenerationId,
  readProgress,
  readResultUrl,
  readSeed,
  readUpscaleRemaining,
  readWarningMessage,
  toHistoryItem,
} from "@/lib/generation-contract";
import type {AspectRatioValue, StylePresetValue} from "@/lib/studio-config";

export type GenerationStatus =
  | "idle"
  | "queued"
  | "processing"
  | "done"
  | "failed"
  | "canceled";

export type GenerationMode = "generate" | "edit";

export type HistoryItem = GenerationRecord;

export type GenerationErrorMessages = {
  http: (status: number) => string;
  failed: string;
  network: string;
};

type GenerationState = {
  prompt: string;
  mode: GenerationMode;
  aspectRatio: AspectRatioValue;
  stylePreset: StylePresetValue;
  seed: string;
  uploadFile: File | null;
  imageBase64: string | undefined;
  status: GenerationStatus;
  progress: number;
  result: GenerationRecord | null;
  resultUrl: string | null;
  error: string | null;
  warning: string | null;
  history: HistoryItem[];
  historyCursor: string | null;
  historyLoading: boolean;
  upscaleRemaining: number | null;
  startGeneration: (
    prompt: string,
    errors: GenerationErrorMessages,
    locale?: string,
  ) => Promise<void>;
  startEditUpload: (
    prompt: string,
    errors: GenerationErrorMessages,
    locale?: string,
  ) => Promise<void>;
  startUpscale: (
    generationId: string,
    errors: GenerationErrorMessages,
    locale?: string,
  ) => Promise<void>;
  startVariation: (
    generationId: string,
    errors: GenerationErrorMessages,
    locale?: string,
  ) => Promise<void>;
  startRefine: (
    generationId: string,
    instruction: string,
    aspectRatio: AspectRatioValue,
    errors: GenerationErrorMessages,
    locale?: string,
  ) => Promise<void>;
  loadHistory: (reset?: boolean) => Promise<void>;
  showResult: (item: GenerationRecord) => void;
  cancelGeneration: (errors: GenerationErrorMessages) => Promise<void>;
  reset: () => void;
  setPrompt: (p: string) => void;
  setMode: (mode: GenerationMode) => void;
  setAspectRatio: (ratio: AspectRatioValue) => void;
  setStylePreset: (preset: StylePresetValue) => void;
  setSeed: (seed: string) => void;
  setUploadFile: (file: File | null) => void;
  setImage: (image: string | undefined) => void;
};

export function isGeneratingStatus(status: GenerationStatus): boolean {
  return status === "queued" || status === "processing";
}

export function parseSeedInput(seed: string): number | undefined {
  const value = seed.trim();
  if (!value) return undefined;
  if (!/^\d+$/.test(value)) return undefined;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > 2 ** 32 - 1) {
    return undefined;
  }
  return parsed;
}

async function ensureAnonymousToken(): Promise<void> {
  if (getAccessToken() || getAnonymousToken()) return;
  try {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/prompt-quota`, {
      cache: "no-store",
    });
    if (!response.ok) return;
    const data = (await response.json()) as {anonymous_token?: unknown};
    if (typeof data.anonymous_token === "string" && data.anonymous_token) {
      saveAnonymousToken(data.anonymous_token);
    }
  } catch {
    // Sem token o POST ainda pode criar a sessao; se falhar, o erro real aparece.
  }
}

let source: EventSource | null = null;

function closeSource() {
  source?.close();
  source = null;
}

type SetState = (
  partial:
    | Partial<GenerationState>
    | ((state: GenerationState) => Partial<GenerationState>),
) => void;

type GetState = () => GenerationState;

async function connectStream(
  streamPath: string,
  generationId: string,
  locale: string | undefined,
  errors: GenerationErrorMessages,
  set: SetState,
  get: GetState,
) {
  closeSource();
  try {
    const headers = new Headers();
    if (locale) headers.set("X-Locale", locale);
    const anon = getAnonymousToken();
    if (anon) headers.set("X-Anonymous-Session", anon);
    const ticketResponse = await authedFetch(
      `${API_BASE_URL}/api/v1/generations/${encodeURIComponent(generationId)}/stream-ticket`,
      {method: "POST", headers},
    );
    if (!ticketResponse.ok) {
      set({status: "failed", error: await readFailure(ticketResponse, errors)});
      return;
    }
    const ticketData = (await ticketResponse.json()) as {
      ticket?: unknown;
      stream_url?: unknown;
    };
    if (
      typeof ticketData.ticket !== "string" ||
      typeof ticketData.stream_url !== "string"
    ) {
      set({status: "failed", error: errors.failed});
      return;
    }
    const absolute = ticketData.stream_url.startsWith("http")
      ? ticketData.stream_url
      : `${API_BASE_URL}${ticketData.stream_url}`;
    const params = new URLSearchParams({ticket: ticketData.ticket});
    if (locale) params.set("locale", locale);
    source = new EventSource(`${absolute}?${params.toString()}`);
  } catch {
    set({status: "failed", error: errors.network});
    return;
  }
  source.addEventListener("status_update", (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as {
      status: GenerationStatus;
    };
    set({status: payload.status});
  });
  source.addEventListener("progress", (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as unknown;
    set({status: "processing", progress: readProgress(payload) ?? 0});
  });
  source.addEventListener("result", (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as unknown;
    closeSource();
    const current = get().result;
    const url = readResultUrl(payload);
    set({
      status: "done",
      progress: 100,
      resultUrl: url,
      result: current
        ? {
            ...current,
            status: "done",
            imageUrl: url ?? current.imageUrl,
            seed: readSeed(payload) ?? current.seed,
            parentGenerationId:
              readParentGenerationId(payload) ?? current.parentGenerationId,
          }
        : current,
    });
    if (getAccessToken()) void get().loadHistory(true);
  });
  source.addEventListener("error", (event) => {
    closeSource();
    let message = errors.failed;
    let warning: string | null = null;
    try {
      const payload = JSON.parse((event as MessageEvent).data) as unknown;
      message = readErrorMessage(payload) ?? message;
      warning = readWarningMessage(payload);
    } catch {
      // evento nativo de rede do EventSource: manter fallback localizado
    }
    set({status: "failed", error: message, warning});
    if (getAccessToken()) void get().loadHistory(true);
  });
}

async function readFailure(
  response: Response,
  errors: GenerationErrorMessages,
): Promise<string> {
  try {
    const apiError = readApiError(await response.json());
    return apiError.message ?? apiError.code ?? errors.http(response.status);
  } catch {
    return errors.http(response.status);
  }
}

export const useGenerationStore = create<GenerationState>((set, get) => ({
  prompt: "",
  mode: "generate",
  aspectRatio: "1:1",
  stylePreset: "none",
  seed: "",
  uploadFile: null,
  imageBase64: undefined,
  status: "idle",
  progress: 0,
  result: null,
  resultUrl: null,
  error: null,
  warning: null,
  history: [],
  historyCursor: null,
  historyLoading: false,
  upscaleRemaining: null,

  setPrompt: (prompt) => set({prompt}),
  setMode: (mode) => set({mode}),
  setAspectRatio: (aspectRatio) => set({aspectRatio}),
  setStylePreset: (stylePreset) => set({stylePreset}),
  setSeed: (seed) => set({seed}),
  setUploadFile: (uploadFile) => set({uploadFile}),
  setImage: (imageBase64) => set({imageBase64}),

  showResult: (item) =>
    set({
      prompt: item.prompt,
      result: item,
      resultUrl: item.imageUrl,
      status:
        item.status === "failed"
          ? "failed"
          : item.status === "queued"
            ? "queued"
            : item.status === "processing"
              ? "processing"
              : "done",
      error: null,
      warning: null,
    }),

  reset: () => {
    closeSource();
    set({
      prompt: "",
      mode: "generate",
      aspectRatio: "1:1",
      seed: "",
      uploadFile: null,
      imageBase64: undefined,
      status: "idle",
      progress: 0,
      result: null,
      resultUrl: null,
      error: null,
      warning: null,
      upscaleRemaining: null,
    });
  },

  async startGeneration(prompt, errors, locale) {
    await ensureAnonymousToken();
    closeSource();
    set({
      prompt,
      status: "queued",
      progress: 0,
      result: null,
      resultUrl: null,
      error: null,
      warning: null,
    });
    try {
      const headers = new Headers({"content-type": "application/json"});
      if (locale) headers.set("X-Locale", locale);
      const anonToken = getAnonymousToken();
      if (anonToken) headers.set("X-Anonymous-Session", anonToken);
      const body: Record<string, unknown> = {
        prompt,
        aspect_ratio: get().aspectRatio,
        style_preset: get().stylePreset,
      };
      const seed = parseSeedInput(get().seed);
      if (seed !== undefined) body.seed = seed;
      const res = await authedFetch(`${API_BASE_URL}/api/v1/generations`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        set({status: "failed", error: await readFailure(res, errors)});
        return;
      }
      const data = (await res.json()) as unknown;
      const created = parseGenerationOutput(data);
      if (!created || typeof (data as {stream_url?: unknown}).stream_url !== "string") {
        set({status: "failed", error: errors.failed});
        return;
      }
      set({result: created, resultUrl: created.imageUrl});
      void connectStream(
        (data as {stream_url: string}).stream_url,
        created.id,
        locale,
        errors,
        set,
        get,
      );
    } catch {
      set({status: "failed", error: errors.network});
    }
  },

  async startEditUpload(prompt, errors, locale) {
    const file = get().uploadFile;
    if (!file) {
      set({status: "failed", error: errors.failed});
      return;
    }
    closeSource();
    set({
      prompt,
      mode: "edit",
      status: "queued",
      progress: 0,
      result: null,
      resultUrl: null,
      error: null,
      warning: null,
    });
    try {
      const headers = new Headers();
      if (locale) headers.set("X-Locale", locale);
      const anonToken = getAnonymousToken();
      if (anonToken) headers.set("X-Anonymous-Session", anonToken);
      const seed = parseSeedInput(get().seed);
      const form = buildEditImageUploadForm(file, prompt, file.name, {
        aspectRatio: get().aspectRatio,
        seed,
      });
      const res = await authedFetch(
        `${API_BASE_URL}/api/v1/generations/edits/upload`,
        {method: "POST", headers, body: form},
      );
      if (!res.ok) {
        set({status: "failed", error: await readFailure(res, errors)});
        return;
      }
      const data = (await res.json()) as unknown;
      const created = parseGenerationOutput(data);
      if (!created || typeof (data as {stream_url?: unknown}).stream_url !== "string") {
        set({status: "failed", error: errors.failed});
        return;
      }
      set({result: created, resultUrl: created.imageUrl});
      void connectStream(
        (data as {stream_url: string}).stream_url,
        created.id,
        locale,
        errors,
        set,
        get,
      );
    } catch {
      set({status: "failed", error: errors.network});
    }
  },

  async startUpscale(generationId, errors, locale) {
    closeSource();
    set({
      status: "queued",
      progress: 0,
      error: null,
      warning: null,
    });
    try {
      const headers = new Headers();
      if (locale) headers.set("X-Locale", locale);
      const res = await authedFetch(
        `${API_BASE_URL}/api/v1/generations/${encodeURIComponent(generationId)}/upscale`,
        {method: "POST", headers},
      );
      if (!res.ok) {
        set({status: "failed", error: await readFailure(res, errors)});
        return;
      }
      const data = (await res.json()) as unknown;
      const created = parseGenerationOutput(data);
      if (!created || typeof (data as {stream_url?: unknown}).stream_url !== "string") {
        set({status: "failed", error: errors.failed});
        return;
      }
      set({
        result: created,
        resultUrl: created.imageUrl,
        upscaleRemaining: readUpscaleRemaining(data),
      });
      void connectStream(
        (data as {stream_url: string}).stream_url,
        created.id,
        locale,
        errors,
        set,
        get,
      );
    } catch {
      set({status: "failed", error: errors.network});
    }
  },

  async cancelGeneration(errors) {
    const current = get().result;
    if (!current || !isGeneratingStatus(get().status)) return;
    const res = await authedFetch(
      `${API_BASE_URL}/api/v1/generations/${encodeURIComponent(current.id)}/cancel`,
      {method: "POST"},
    );
    if (!res.ok) {
      set({error: await readFailure(res, errors)});
      return;
    }
    set({status: "canceled", error: null});
  },

  async startVariation(generationId, errors, locale) {
    closeSource();
    set({
      status: "queued",
      progress: 0,
      error: null,
      warning: null,
    });
    try {
      const headers = new Headers();
      if (locale) headers.set("X-Locale", locale);
      const anonToken = getAnonymousToken();
      if (anonToken) headers.set("X-Anonymous-Session", anonToken);
      const res = await authedFetch(
        `${API_BASE_URL}/api/v1/generations/${encodeURIComponent(generationId)}/variations`,
        {method: "POST", headers},
      );
      if (!res.ok) {
        set({status: "failed", error: await readFailure(res, errors)});
        return;
      }
      const data = (await res.json()) as unknown;
      const created = parseGenerationOutput(data);
      if (!created || typeof (data as {stream_url?: unknown}).stream_url !== "string") {
        set({status: "failed", error: errors.failed});
        return;
      }
      set({result: created, resultUrl: created.imageUrl, prompt: created.prompt});
      void connectStream(
        (data as {stream_url: string}).stream_url,
        created.id,
        locale,
        errors,
        set,
        get,
      );
    } catch {
      set({status: "failed", error: errors.network});
    }
  },

  async startRefine(generationId, instruction, aspectRatio, errors, locale) {
    closeSource();
    set({
      prompt: instruction,
      mode: "edit",
      status: "queued",
      progress: 0,
      error: null,
      warning: null,
    });
    try {
      const headers = new Headers({"content-type": "application/json"});
      if (locale) headers.set("X-Locale", locale);
      const res = await authedFetch(`${API_BASE_URL}/api/v1/generations/edits`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt: instruction,
          source_generation_id: generationId,
          aspect_ratio: aspectRatio,
        }),
      });
      if (!res.ok) {
        set({status: "failed", error: await readFailure(res, errors)});
        return;
      }
      const data = (await res.json()) as unknown;
      const created = parseGenerationOutput(data);
      if (!created || typeof (data as {stream_url?: unknown}).stream_url !== "string") {
        set({status: "failed", error: errors.failed});
        return;
      }
      set({result: created, resultUrl: created.imageUrl});
      void connectStream(
        (data as {stream_url: string}).stream_url,
        created.id,
        locale,
        errors,
        set,
        get,
      );
    } catch {
      set({status: "failed", error: errors.network});
    }
  },

  async loadHistory(reset = false) {
    if (!getAccessToken()) return;
    const cursor = reset ? null : get().historyCursor;
    const params = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    set({historyLoading: true});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/generations${params}`);
      if (!res.ok) return;
      const data = (await res.json()) as {
        items: ApiGenerationItem[];
        next_cursor: string | null;
      };
      const items = data.items.map(toHistoryItem);
      set({
        history: reset ? items : [...get().history, ...items],
        historyCursor: readNextCursor(data),
      });
    } finally {
      set({historyLoading: false});
    }
  },
}));
