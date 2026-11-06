import {expect, test, type Page} from "@playwright/test";

const API = /\/api\/v1\//;
const TINY_PNG =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAC0lEQVR4AWNgQAYAAA4AAZ3EcOgAAAAASUVORK5CYII=";

type SseEvent = {type: string; data: Record<string, unknown>};
type Captured = {method: string; path: string; body: string | null; contentType: string | null};

function generation(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    kind: "generate",
    status: "queued",
    prompt: "um castelo nas nuvens",
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

async function mockApi(
  page: Page,
  options: {
    authenticated?: boolean;
    featureEnabled?: boolean;
    events: SseEvent[];
    historyItems?: unknown[];
  },
) {
  const captured: Captured[] = [];
  await page.addInitScript((events) => {
    (window as unknown as {__sseEvents: SseEvent[]}).__sseEvents = events;
    class MockEventSource {
      private closed = false;
      private listeners = new Map<string, ((event: MessageEvent) => void)[]>();
      constructor(public url: string) {
        const list =
          (window as unknown as {__sseEvents?: SseEvent[]}).__sseEvents ?? [];
        let delay = 25;
        for (const item of list) {
          window.setTimeout(() => this.emit(item.type, item.data), delay);
          delay += 25;
        }
      }
      addEventListener(type: string, listener: (event: MessageEvent) => void) {
        const current = this.listeners.get(type) ?? [];
        current.push(listener);
        this.listeners.set(type, current);
      }
      close() {
        this.closed = true;
      }
      private emit(type: string, data: Record<string, unknown>) {
        if (this.closed) return;
        for (const listener of this.listeners.get(type) ?? []) {
          listener(new MessageEvent(type, {data: JSON.stringify(data)}));
        }
      }
    }
    Object.defineProperty(window, "EventSource", {value: MockEventSource});
  }, options.events);

  if (options.authenticated) {
    await page.addInitScript(() => {
      window.localStorage.setItem("aimaginator.access_token", "test-token");
      window.localStorage.setItem("aimaginator.refresh_token", "refresh-token");
    });
  }

  await page.route(API, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    captured.push({
      method,
      path: url.pathname,
      body: request.postData(),
      contentType: request.headers()["content-type"] ?? null,
    });

    if (url.pathname === "/api/v1/config") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          image_generation_enabled: options.featureEnabled ?? true,
          upload_max_bytes: 10485760,
          upload_max_dimension: 8192,
          upload_max_pixels: 40000000,
        }),
      });
      return;
    }

    if (url.pathname.endsWith("/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          name: "Ada Lovelace",
          email: "ada@example.com",
          avatar_url: null,
          google_sub: null,
          bio: null,
          handle: null,
        }),
      });
      return;
    }

    if (url.pathname === "/api/v1/generations" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: options.historyItems ?? [],
          next_cursor: null,
        }),
      });
      return;
    }

    if (url.pathname.match(/\/generations\/[^/]+\/stream-ticket$/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ticket: "ticket-test-123456",
          stream_url: url.pathname.replace("/stream-ticket", "/stream"),
          expires_in: 60,
        }),
      });
      return;
    }

    if (url.pathname.match(/\/generations\/[^/]+\/upscale$/)) {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify(
          generation("upscale-1", {
            kind: "upscale",
            parent_generation_id: "gen-1",
            upscale_remaining: 4,
          }),
        ),
      });
      return;
    }

    if (url.pathname.match(/\/generations\/[^/]+\/variations$/)) {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify(
          generation("variation-1", {
            prompt: "um castelo nas nuvens",
            seed: 888,
          }),
        ),
      });
      return;
    }

    if (url.pathname.endsWith("/generations/edits") && method === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify(
          generation("refine-1", {
            kind: "edit",
            prompt: "deixe o ceu alaranjado",
            parent_generation_id: "gen-1",
          }),
        ),
      });
      return;
    }

    if (url.pathname.endsWith("/generations/edits/upload")) {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify(
          generation("upload-1", {kind: "edit", prompt: "edite a imagem"}),
        ),
      });
      return;
    }

    if (url.pathname === "/api/v1/generations" && method === "POST") {
      const payload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify(
          generation("gen-1", {
            prompt: payload.prompt,
            aspect_ratio: payload.aspect_ratio,
            seed: payload.seed ?? null,
          }),
        ),
      });
      return;
    }

    await route.fulfill({status: 404, contentType: "application/json", body: "{}"});
  });

  return captured;
}

async function gotoStudio(page: Page, locale = "pt-BR") {
  await page.goto(`/${locale}/studio`);
  await expect(page.getByRole("heading", {level: 1})).toBeVisible();
}

const progressEvents: SseEvent[] = [
  {type: "status_update", data: {status: "processing"}},
  {type: "progress", data: {progress: 35}},
  {type: "progress", data: {progress: 80}},
  {
    type: "result",
    data: {
      result_image_url: TINY_PNG,
      seed: 1234,
      parent_generation_id: null,
    },
  },
];

test.describe("studio", () => {
  test("selects aspect ratio and seed, generates and shows progress", async ({
    page,
  }) => {
    const captured = await mockApi(page, {
      authenticated: true,
      events: progressEvents,
    });
    await gotoStudio(page);

    await page.getByRole("radio", {name: /4:3/}).click();
    await expect(page.getByRole("radio", {name: /4:3/})).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByText("Proporção: 4:3")).toBeVisible();

    await page.getByText("Opções avançadas").click();
    await page.getByLabel("Seed").fill("123");
    await page.getByLabel("Prompt").fill("um castelo nas nuvens");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();

    await expect(page.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
    await expect(page.getByRole("img", {name: "um castelo nas nuvens"}).first()).toBeVisible();
    await expect(page.getByText("Seed: 1234")).toBeVisible();

    const post = captured.find(
      (item) => item.method === "POST" && item.path === "/api/v1/generations",
    );
    expect(JSON.parse(post?.body ?? "{}")).toMatchObject({
      prompt: "um castelo nas nuvens",
      aspect_ratio: "4:3",
      seed: 123,
    });
  });

  test("generates a variation and refines the result", async ({page}) => {
    const captured = await mockApi(page, {
      authenticated: true,
      events: progressEvents,
    });
    await gotoStudio(page);
    await page.getByLabel("Prompt").fill("um castelo nas nuvens");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();
    await expect(page.getByRole("img", {name: "um castelo nas nuvens"}).first()).toBeVisible();

    await page.getByRole("button", {name: "Gerar variação"}).click();
    await expect
      .poll(() => captured.some((item) => item.path.endsWith("/variations")))
      .toBe(true);

    await expect(page.getByRole("button", {name: "Refinar"}).first()).toBeVisible();
    await page.getByRole("button", {name: "Refinar"}).first().click();
    await page.getByLabel("O que deve mudar?").fill("deixe o ceu alaranjado");
    await page.getByRole("button", {name: "Aplicar refinamento"}).click();
    await expect
      .poll(() => captured.some((item) => item.path.endsWith("/generations/edits")))
      .toBe(true);
    const refine = captured.find((item) => item.path.endsWith("/generations/edits"));
    expect(JSON.parse(refine?.body ?? "{}")).toMatchObject({
      prompt: "deixe o ceu alaranjado",
      source_generation_id: "variation-1",
      aspect_ratio: "1:1",
    });
  });

  test("validates upload type and sends a valid PNG in edit mode", async ({page}) => {
    const captured = await mockApi(page, {
      authenticated: true,
      events: progressEvents,
    });
    await gotoStudio(page);
    await page.getByRole("tab", {name: "Editar imagem"}).click();

    const input = page.locator('input[type="file"]').first();
    await input.setInputFiles({
      name: "bad.gif",
      mimeType: "image/gif",
      buffer: Buffer.from("GIF89a"),
    });
    await expect(page.getByText(/Apenas imagens PNG ou JPEG/)).toBeVisible();

    await input.setInputFiles({
      name: "ok.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAC0lEQVR4AWNgQAYAAA4AAZ3EcOgAAAAASUVORK5CYII=",
        "base64",
      ),
    });
    await expect(page.getByAltText("Imagem de origem selecionada")).toBeVisible();
    await page.getByLabel("Instrução de edição").fill("edite a imagem");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();

    await expect
      .poll(() => captured.some((item) => item.path.endsWith("/edits/upload")))
      .toBe(true);
    const upload = captured.find((item) => item.path.endsWith("/edits/upload"));
    expect(upload?.contentType).toContain("multipart/form-data");
  });

  test("shows the localized backend refusal and warning", async ({page}) => {
    await mockApi(page, {
      authenticated: true,
      events: [
        {
          type: "error",
          data: {
            error: "The generated image was blocked by the content policy.",
            error_code: "image_blocked_nsfw",
            warning_level: null,
            warning_message: null,
          },
        },
      ],
    });
    await gotoStudio(page, "en");
    await page.getByLabel("Prompt").fill("explicit request");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();
    await expect(
      page.getByText(/The generated image was blocked by the content policy\./),
    ).toBeVisible();
  });

  test("upscales a result and shows the remaining daily limit", async ({page}) => {
    const captured = await mockApi(page, {
      authenticated: true,
      events: progressEvents,
    });
    await gotoStudio(page);
    await page.getByLabel("Prompt").fill("um castelo nas nuvens");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();
    await expect(page.getByRole("img", {name: "um castelo nas nuvens"}).first()).toBeVisible();

    await page.getByRole("button", {name: "Ampliar"}).click();
    await expect
      .poll(() => captured.some((item) => item.path.endsWith("/upscale")))
      .toBe(true);
    await expect(page.getByText("Ampliações restantes hoje: 4")).toBeVisible();
    await expect(page.getByRole("link", {name: "Baixar"})).toHaveAttribute(
      "href",
      /data:image\/png/,
    );
  });

  test("shows the coming-soon state when the feature flag is off", async ({
    page,
  }) => {
    await mockApi(page, {
      authenticated: true,
      featureEnabled: false,
      events: progressEvents,
    });
    await gotoStudio(page);
    await expect(page.getByText(/ainda não está disponível/)).toBeVisible();
    await expect(
      page.locator('[data-testid="studio-form"] button[type="submit"]'),
    ).toBeDisabled();
  });

  test("anonymous users cannot edit but can still generate", async ({page}) => {
    await mockApi(page, {authenticated: false, events: progressEvents});
    await gotoStudio(page);
    await expect(page.getByRole("tab", {name: "Editar imagem"})).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await expect(page.getByText("Entre para editar ou refinar imagens.")).toBeVisible();
    await page.getByLabel("Prompt").fill("um castelo");
    await page.locator('[data-testid="studio-form"] button[type="submit"]').click();
    await expect(page.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
  });

  test("renders history with parent chain and actions", async ({page}) => {
    await mockApi(page, {
      authenticated: true,
      events: progressEvents,
      historyItems: [
        {
          id: "parent-1",
          kind: "generate",
          status: "done",
          prompt: "um castelo",
          aspect_ratio: "1:1",
          seed: 1,
          parent_generation_id: null,
          result_image_url: TINY_PNG,
          created_at: "2026-11-06T10:00:00Z",
          completed_at: "2026-11-06T10:01:00Z",
          title: null,
        },
        {
          id: "child-1",
          kind: "edit",
          status: "done",
          prompt: "mude o ceu",
          aspect_ratio: "4:3",
          seed: 2,
          parent_generation_id: "parent-1",
          result_image_url: TINY_PNG,
          created_at: "2026-11-06T11:00:00Z",
          completed_at: "2026-11-06T11:01:00Z",
          title: null,
        },
      ],
    });
    await gotoStudio(page);
    await expect(page.getByText("mude o ceu")).toBeVisible();
    await expect(page.getByText("Refinamento de: um castelo")).toBeVisible();
    await expect(page.getByRole("button", {name: "Abrir"})).toHaveCount(2);
    await expect(page.getByRole("button", {name: "Variação"})).toHaveCount(1);
    await expect(page.getByRole("button", {name: "Refinar"})).toHaveCount(2);
  });

  test("switches language including RTL Arabic, Japanese and Korean", async ({
    page,
  }) => {
    await mockApi(page, {authenticated: false, events: progressEvents});
    await gotoStudio(page, "pt-BR");

    await page.locator('button[aria-haspopup="listbox"]').click();
    await page.getByRole("option", {name: /Italiano/}).click();
    await expect(page).toHaveURL(/\/it\/studio/);

    await page.locator('button[aria-haspopup="listbox"]').click();
    await page.getByRole("option", {name: /العربية/}).click();
    await expect(page).toHaveURL(/\/ar\/studio/);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

    await page.locator('button[aria-haspopup="listbox"]').click();
    await page.getByRole("option", {name: /日本語/}).click();
    await expect(page).toHaveURL(/\/ja\/studio/);
    await expect(page.locator("html")).toHaveAttribute("lang", "ja");

    await page.locator('button[aria-haspopup="listbox"]').click();
    await page.getByRole("option", {name: /한국어/}).click();
    await expect(page).toHaveURL(/\/ko\/studio/);
    await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  });
});
