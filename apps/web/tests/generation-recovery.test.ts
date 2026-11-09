import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
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

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {"content-type": "application/json"},
  });
}

function createdGeneration() {
  return {
    id: "g1",
    kind: "generate",
    status: "queued",
    prompt: "cabana",
    aspect_ratio: "1:1",
    seed: null,
    parent_generation_id: null,
    result_image_url: null,
    error_message: null,
    created_at: "2026-11-09T12:00:00Z",
    completed_at: null,
    stream_url: "/api/v1/generations/g1/stream",
  };
}

const errors = {
  http: (status: number) => `http ${status}`,
  failed: "failed",
  network: "network",
  alreadyFinished: "already finished",
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  useGenerationStore.setState({
    prompt: "",
    mode: "generate",
    aspectRatio: "1:1",
    seed: "",
    uploadFile: null,
    status: "idle",
    progress: 0,
    stage: null,
    streamDegraded: false,
    canceling: false,
    result: null,
    resultUrl: null,
    error: null,
    warning: null,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("generation stream recovery", () => {
  it("faz polling com backoff e conclui quando o SSE cai", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/prompt-quota")) {
        return jsonResponse({anonymous_token: "anon-test"});
      }
      if (url.includes("/stream-ticket")) {
        return jsonResponse({
          ticket: "ticket-test-1234567890",
          stream_url: "/api/v1/generations/g1/stream",
          expires_in: 60,
        });
      }
      if (url.match(/\/api\/v1\/generations\/g1$/)) {
        return jsonResponse({
          ...createdGeneration(),
          status: "done",
          result_image_url: "https://cdn.example/result.png",
        });
      }
      return jsonResponse(createdGeneration(), 202);
    });
    vi.stubGlobal("fetch", fetchMock);

    await useGenerationStore
      .getState()
      .startGeneration("cabana", errors, "pt-BR");
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));

    FakeEventSource.instances[0].emit("error", {});
    await vi.advanceTimersByTimeAsync(1100);
    await vi.advanceTimersByTimeAsync(0);

    await vi.waitFor(() => {
      expect(useGenerationStore.getState().status).toBe("done");
    });
    expect(useGenerationStore.getState().resultUrl).toBe(
      "https://cdn.example/result.png",
    );
    expect(useGenerationStore.getState().streamDegraded).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/api/v1/generations/g1"),
      ),
    ).toBe(true);
  });
});
