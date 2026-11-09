export type ApiError = {
  code: string | null;
  message: string | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

export function readApiError(payload: unknown): ApiError {
  const root = asRecord(payload);
  const error = root ? asRecord(root.error) : null;
  const code = error && typeof error.code === "string" ? error.code : null;
  const message = error && typeof error.message === "string" ? error.message : null;
  return {code, message};
}

export function readProgress(payload: unknown): number | null {
  const record = asRecord(payload);
  const value = record?.progress;
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function readResultUrl(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.result_image_url;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function readStage(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.stage;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function readStatus(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.status;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function readErrorMessage(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.error ?? record?.error_message;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function readNextCursor(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.next_cursor;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export type GenerationRecord = {
  id: string;
  kind: "generate" | "edit" | "upscale";
  status: string;
  prompt: string;
  aspectRatio: string;
  seed: number | null;
  parentGenerationId: string | null;
  imageUrl: string | null;
  createdAt: string;
  completedAt: string | null;
  title: string | null;
};

export type ApiGenerationItem = {
  id: string;
  kind?: string;
  status?: string;
  prompt: string;
  aspect_ratio?: string;
  seed?: number | null;
  parent_generation_id?: string | null;
  result_image_url?: string | null;
  created_at?: string;
  completed_at?: string | null;
  title?: string | null;
};

export function toHistoryItem(item: ApiGenerationItem): GenerationRecord {
  return {
    id: item.id,
    kind:
      item.kind === "edit"
        ? "edit"
        : item.kind === "upscale"
          ? "upscale"
          : "generate",
    status: item.status ?? "done",
    prompt: item.prompt,
    aspectRatio: item.aspect_ratio ?? "1:1",
    seed: typeof item.seed === "number" ? item.seed : null,
    parentGenerationId: item.parent_generation_id ?? null,
    imageUrl: item.result_image_url ?? null,
    createdAt: item.created_at ?? "",
    completedAt: item.completed_at ?? null,
    title: item.title ?? null,
  };
}

export function parseGenerationOutput(payload: unknown): GenerationRecord | null {
  const record = asRecord(payload);
  if (!record || typeof record.id !== "string" || typeof record.prompt !== "string") {
    return null;
  }
  return toHistoryItem(record as ApiGenerationItem);
}

export function readUpscaleRemaining(payload: unknown): number | null {
  const record = asRecord(payload);
  return typeof record?.upscale_remaining === "number"
    ? record.upscale_remaining
    : null;
}

export function readSeed(payload: unknown): number | null {
  const record = asRecord(payload);
  return typeof record?.seed === "number" ? record.seed : null;
}

export function readParentGenerationId(payload: unknown): string | null {
  const record = asRecord(payload);
  const value = record?.parent_generation_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export type EditUploadOptions = {
  negativePrompt?: string;
  stylePreset?: string;
  aspectRatio?: string;
  seed?: number;
  title?: string;
};

export function buildEditImageUploadForm(
  file: Blob,
  prompt: string,
  filename = "image.png",
  options: EditUploadOptions = {},
): FormData {
  const form = new FormData();
  form.append("file", file, filename);
  form.append("prompt", prompt);
  if (options.negativePrompt) form.append("negative_prompt", options.negativePrompt);
  if (options.stylePreset) form.append("style_preset", options.stylePreset);
  if (options.aspectRatio) form.append("aspect_ratio", options.aspectRatio);
  if (typeof options.seed === "number") form.append("seed", String(options.seed));
  if (options.title) form.append("title", options.title);
  return form;
}

export type EditGenerationInfo = {
  id: string;
  kind: string;
  status: string;
  streamUrl: string | null;
};

export function parseEditGeneration(payload: unknown): EditGenerationInfo | null {
  const record = asRecord(payload);
  if (!record) return null;
  const {id, kind, status, stream_url} = record;
  if (typeof id !== "string" || typeof kind !== "string" || typeof status !== "string") {
    return null;
  }
  return {id, kind, status, streamUrl: typeof stream_url === "string" ? stream_url : null};
}

export function readWarningMessage(payload: unknown): string | null {
  const record = asRecord(payload);
  if (!record) return null;
  const direct = record.warning_message;
  if (typeof direct === "string" && direct.length > 0) return direct;
  const error = asRecord(record.error);
  const nested = error?.warning_message;
  return typeof nested === "string" && nested.length > 0 ? nested : null;
}

export function readErrorCode(payload: unknown): string | null {
  const envelope = readApiError(payload);
  if (envelope.code) return envelope.code;
  const record = asRecord(payload);
  const value = record?.error_code;
  return typeof value === "string" && value.length > 0 ? value : null;
}
