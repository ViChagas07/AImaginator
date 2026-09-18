import {beforeEach, describe, expect, it, vi} from "vitest";
import {useAuthStore} from "../stores/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({user: null, status: "unknown"});
    window.localStorage.clear();
  });

  it("signIn salva a sessao e define o usuario autenticado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: "access-123",
          refresh_token: "refresh-123",
          user: {id: "1", name: "Ada", email: "ada@example.com", avatarUrl: null},
        }),
      }),
    );

    await useAuthStore.getState().signIn("ada@example.com", "senha-segura");

    expect(window.localStorage.getItem("aimaginator.access_token")).toBe("access-123");
    expect(useAuthStore.getState().status).toBe("authenticated");
    expect(useAuthStore.getState().user?.email).toBe("ada@example.com");
  });

  it("signIn propaga erro de credenciais invalidas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({error: {code: "unauthorized"}}),
      }),
    );

    await expect(
      useAuthStore.getState().signIn("ada@example.com", "errada"),
    ).rejects.toThrow();
    expect(useAuthStore.getState().status).toBe("unknown");
  });
});
