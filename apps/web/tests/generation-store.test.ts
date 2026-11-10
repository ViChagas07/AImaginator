import {beforeEach, describe, expect, it, vi} from "vitest";
import {useGenerationStore} from "../stores/generation";

type Listener = (event: MessageEvent) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners = new Map<string, Listener[]>();
  closed = false;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data: Record<string, unknown>) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, {data: JSON.stringify(data)}));
    }
  }
}

function generation(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    kind: "generate",
    status: "queued",
    prompt: "um castelo",
    aspect_ratio: "1:1",
    seed: null,
    parent_generation_id: null,
    result_image_url: null,
    error_message: null,
    created_at: "2026-11-06T12:00:00Z",
    completed_at: null,
    stream_url: `/api/v1/generations/${id}/stream`,
    ...overrides,
  };
}

function mockFetch(created: unknown) {
  return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    void _init;
    const url = String(input);
    if (url.includes("/stream-ticket")) {
      const id = url.split("/generations/")[1]?.split("/")[0] ?? "g1";
      return jsonResponse(
        {
          ticket: "ticket-test-1234567890",
          stream_url: `/api/v1/generations/${id}/stream`,
          expires_in: 60,
        },
        200,
      );
    }
    return jsonResponse(created);
  });
}

function jsonResponse(body: unknown, status = 202) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {"content-type": "application/json"},
  });
}

const errors = {
  http: (status: number) => `http ${status}`,
  failed: "failed",
  network: "network",
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.removeItem("aimaginator.access_token");
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  window.localStorage.removeItem("aimaginator.anonymous_session");
  useGenerationStore.setState({
    prompt: "",
    mode: "generate",
    aspectRatio: "1:1",
    seed: "",
    uploadFile: null,
    status: "idle",
    progress: 0,
    result: null,
    resultUrl: null,
    sessionResults: [],
    error: null,
    warning: null,
  });
});

describe("generation store", () => {
  it("sends aspect_ratio and seed and opens the SSE stream", async () => {
    const fetchMock = mockFetch(
      generation("g1", {aspect_ratio: "4:3", seed: 42}),
    );
    vi.stubGlobal("fetch", fetchMock);
    useGenerationStore.setState({aspectRatio: "4:3", seed: "42"});

    await useGenerationStore.getState().startGeneration("um castelo", errors, "pt-BR");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/generations");
    expect(JSON.parse(String(init?.body ?? "{}"))).toEqual({
      prompt: "um castelo",
      aspect_ratio: "4:3",
      style_preset: "none",
      seed: 42,
    });
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(FakeEventSource.instances[0].url).toContain("/api/v1/generations/g1/stream");
    expect(FakeEventSource.instances[0].url).toContain("locale=pt-BR");
  });

  it("starts a variation with POST on the variations endpoint", async () => {
    const fetchMock = mockFetch(generation("v1"));
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore.getState().startVariation("g1", errors, "en");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/generations/g1/variations");
    expect(init?.method).toBe("POST");
  });

  it("starts a chained refinement with source_generation_id", async () => {
    const fetchMock = mockFetch(generation("r1", {kind: "edit"}));
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore
      .getState()
      .startRefine("g1", "deixe o ceu alaranjado", "4:3", errors, "en");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/generations/edits");
    expect(JSON.parse(String(init?.body ?? "{}"))).toEqual({
      prompt: "deixe o ceu alaranjado",
      source_generation_id: "g1",
      aspect_ratio: "4:3",
    });
  });

  it("starts an upscale and stores the remaining limit", async () => {
    window.localStorage.setItem("aimaginator.access_token", "token");
    const fetchMock = mockFetch(
      generation("u1", {kind: "upscale", upscale_remaining: 4}),
    );
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore.getState().startUpscale("g1", errors, "pt-BR");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/generations/g1/upscale");
    expect(init?.method).toBe("POST");
    expect(useGenerationStore.getState().upscaleRemaining).toBe(4);
  });

  it("loads paginated history", async () => {
    window.localStorage.setItem("aimaginator.access_token", "token");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          items: [
            {
              ...generation("h1", {status: "done", seed: 7}),
              result_image_url: "https://cdn.example/h1.png",
            },
          ],
          next_cursor: "next",
        },
        200,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore.getState().loadHistory(true);

    const state = useGenerationStore.getState();
    expect(state.history).toHaveLength(1);
    expect(state.history[0]).toMatchObject({id: "h1", seed: 7});
    expect(state.historyCursor).toBe("next");
  });

  it("updates result seed and URL from the SSE result event", async () => {
    const fetchMock = mockFetch(generation("g2"));
    vi.stubGlobal("fetch", fetchMock);
    await useGenerationStore.getState().startGeneration("um castelo", errors, "pt-BR");

    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.instances[0];
    stream.emit("progress", {progress: 50});
    stream.emit("result", {
      result_image_url: "https://cdn.example/g2.png",
      seed: 999,
      parent_generation_id: null,
    });

    const state = useGenerationStore.getState();
    expect(state.status).toBe("done");
    expect(state.progress).toBe(100);
    expect(state.resultUrl).toBe("https://cdn.example/g2.png");
    expect(state.result?.seed).toBe(999);
  });

  it("keeps previous images visible and puts the newest first", async () => {
    let created = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/stream-ticket")) {
          const id = url.split("/generations/")[1]?.split("/")[0] ?? "g1";
          return jsonResponse(
            {
              ticket: "ticket-test-1234567890",
              stream_url: `/api/v1/generations/${id}/stream`,
              expires_in: 60,
            },
            200,
          );
        }
        if (init?.method === "PATCH") {
          const id = url.split("/generations/")[1] ?? "g1";
          return jsonResponse(
            generation(id, {
              status: "done",
              title: "Nome novo",
              result_image_url: `https://cdn.example/${id}.png`,
            }),
            200,
          );
        }
        created += 1;
        const id = `g${created}`;
        return jsonResponse(generation(id, {prompt: `prompt ${id}`}));
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore
      .getState()
      .startGeneration("primeiro castelo", errors, "pt-BR");
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    FakeEventSource.instances[0].emit("result", {
      result_image_url: "https://cdn.example/g1.png",
      seed: 1,
      parent_generation_id: null,
    });
    expect(useGenerationStore.getState().sessionResults.map((item) => item.id)).toEqual([
      "g1",
    ]);

    await useGenerationStore
      .getState()
      .startGeneration("segundo castelo", errors, "pt-BR");
    expect(useGenerationStore.getState().sessionResults.map((item) => item.id)).toEqual([
      "g1",
    ]);
    expect(useGenerationStore.getState().resultUrl).toBeNull();

    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    FakeEventSource.instances[1].emit("result", {
      result_image_url: "https://cdn.example/g2.png",
      seed: 2,
      parent_generation_id: null,
    });

    const state = useGenerationStore.getState();
    expect(state.sessionResults.map((item) => item.id)).toEqual(["g2", "g1"]);
    expect(state.sessionResults[0].imageUrl).toBe("https://cdn.example/g2.png");

    window.localStorage.setItem("aimaginator.anonymous_session", "anon-token");
    const renamed = await useGenerationStore
      .getState()
      .renameGeneration("g1", "Nome novo");
    expect(renamed).toBe(true);
    expect(
      useGenerationStore
        .getState()
        .sessionResults.find((item) => item.id === "g1")?.title,
    ).toBe("Nome novo");

    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    const headers = new Headers(patchCall?.[1]?.headers);
    expect(headers.get("X-Anonymous-Session")).toBe("anon-token");
  });
});
