import {describe, expect, it} from "vitest";
import {
  buildEditImageUploadForm,
  parseEditGeneration,
  parseGenerationOutput,
  readApiError,
  readErrorCode,
  readErrorMessage,
  readNextCursor,
  readProgress,
  readParentGenerationId,
  readResultUrl,
  readUpscaleRemaining,
  readSeed,
  readWarningMessage,
  toHistoryItem,
} from "../lib/generation-contract";

describe("generation contract helpers", () => {
  it("reads the backend SSE progress key", () => {
    expect(readProgress({progress: 42})).toBe(42);
    expect(readProgress({percent: 42})).toBeNull();
    expect(readProgress({progress: 120})).toBe(100);
    expect(readProgress({progress: "42"})).toBeNull();
  });

  it("reads result_image_url instead of imageUrl", () => {
    expect(readResultUrl({result_image_url: "https://cdn.example/a.png"})).toBe(
      "https://cdn.example/a.png",
    );
    expect(readResultUrl({imageUrl: "https://cdn.example/a.png"})).toBeNull();
  });

  it("reads the SSE error string", () => {
    expect(readErrorMessage({error: "Falha no processamento."})).toBe(
      "Falha no processamento.",
    );
    expect(readErrorMessage({message: "Falha no processamento."})).toBeNull();
  });

  it("reads next_cursor instead of cursor", () => {
    expect(readNextCursor({next_cursor: "abc"})).toBe("abc");
    expect(readNextCursor({cursor: "abc"})).toBeNull();
  });

  it("reads the backend HTTP error envelope", () => {
    expect(readApiError({error: {code: "out_of_scope", message: "Fora do escopo."}})).toEqual({
      code: "out_of_scope",
      message: "Fora do escopo.",
    });
    expect(readApiError("not-json")).toEqual({code: null, message: null});
  });

  it("maps history items from the backend field names", () => {
    expect(
      toHistoryItem({
        id: "1",
        prompt: "castelo",
        result_image_url: "https://cdn.example/1.png",
        created_at: "2026-01-01T00:00:00Z",
      }),
    ).toEqual({
      id: "1",
      kind: "generate",
      status: "done",
      prompt: "castelo",
      aspectRatio: "1:1",
      seed: null,
      parentGenerationId: null,
      imageUrl: "https://cdn.example/1.png",
      createdAt: "2026-01-01T00:00:00Z",
      completedAt: null,
      title: null,
    });
  });

  it("parses generation output with seed and parent", () => {
    expect(
      parseGenerationOutput({
        id: "gen-2",
        kind: "edit",
        status: "queued",
        prompt: "mude o ceu",
        aspect_ratio: "4:3",
        seed: 42,
        parent_generation_id: "gen-1",
        created_at: "2026-01-01T00:00:00Z",
      }),
    ).toMatchObject({
      id: "gen-2",
      kind: "edit",
      aspectRatio: "4:3",
      seed: 42,
      parentGenerationId: "gen-1",
    });
    expect(parseGenerationOutput({id: "x"})).toBeNull();
    expect(parseGenerationOutput({id: "u", kind: "upscale", prompt: "x"})?.kind).toBe(
      "upscale",
    );
  });

  it("reads SSE seed and parent fields", () => {
    expect(readSeed({seed: 7})).toBe(7);
    expect(readSeed({seed: "7"})).toBeNull();
    expect(readParentGenerationId({parent_generation_id: "p1"})).toBe("p1");
    expect(readParentGenerationId({})).toBeNull();
    expect(readUpscaleRemaining({upscale_remaining: 4})).toBe(4);
    expect(readUpscaleRemaining({})).toBeNull();
  });

  it("builds the multipart edit upload contract with the prompt", () => {
    const file = new Blob([new Uint8Array([1, 2, 3])], {type: "image/png"});
    const form = buildEditImageUploadForm(file, "troque o ceu", "entrada.png", {
      aspectRatio: "4:3",
      seed: 123,
    });
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(form.get("prompt")).toBe("troque o ceu");
    expect(form.get("aspect_ratio")).toBe("4:3");
    expect(form.get("seed")).toBe("123");
  });

  it("parses the edit upload response as a queued generation", () => {
    expect(
      parseEditGeneration({
        id: "gen-1",
        kind: "edit",
        status: "queued",
        stream_url: "/api/v1/generations/gen-1/stream",
      }),
    ).toEqual({
      id: "gen-1",
      kind: "edit",
      status: "queued",
      streamUrl: "/api/v1/generations/gen-1/stream",
    });
    expect(parseEditGeneration({id: "gen-1"})).toBeNull();
  });

  it("reads the localized warning from SSE and HTTP payloads", () => {
    expect(readWarningMessage({error: "x", warning_message: "Aviso localizado"})).toBe(
      "Aviso localizado",
    );
    expect(
      readWarningMessage({error: {code: "x", message: "y", warning_message: "Aviso"}}),
    ).toBe("Aviso");
    expect(readWarningMessage({error: "x"})).toBeNull();
  });

  it("reads the stable error code from HTTP and SSE payloads", () => {
    expect(readErrorCode({error: {code: "engine_timeout", message: "x"}})).toBe(
      "engine_timeout",
    );
    expect(readErrorCode({error: "x", error_code: "engine_oom"})).toBe("engine_oom");
    expect(readErrorCode({error: "x"})).toBeNull();
  });
});
