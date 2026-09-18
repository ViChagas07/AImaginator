import {beforeEach, describe, expect, it, vi} from "vitest";
import {usePromptQuotaStore} from "../stores/prompt-quota";

describe("usePromptQuotaStore", () => {
  beforeEach(() => {
    usePromptQuotaStore.setState({
      loaded: false,
      loading: false,
      chancesRemaining: 0,
      chancesTotal: 1,
      nextAvailableAt: null,
      authenticated: false,
    });
    window.localStorage.clear();
  });

  it("fetch preenche a cota e persiste o token anonimo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          chances_remaining: 0,
          chances_total: 1,
          next_available_at: "2099-01-01T00:00:00Z",
          authenticated: false,
          anonymous_token: "token-assinado",
        }),
      }),
    );

    await usePromptQuotaStore.getState().fetch();

    const state = usePromptQuotaStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.chancesRemaining).toBe(0);
    expect(state.nextAvailableAt).toBe("2099-01-01T00:00:00Z");
    expect(window.localStorage.getItem("aimaginator.anonymous_session")).toBe(
      "token-assinado",
    );
  });

  it("fetch tolera falha de rede sem alterar o estado", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));

    await usePromptQuotaStore.getState().fetch();

    const state = usePromptQuotaStore.getState();
    expect(state.loaded).toBe(false);
    expect(state.loading).toBe(false);
  });
});
