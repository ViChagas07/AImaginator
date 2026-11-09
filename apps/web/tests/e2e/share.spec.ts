import {expect, test} from "@playwright/test";

const png =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl9sAAAAASUVORK5CYII=";

test("public share renders watermarked image and report action", async ({page}) => {
  await page.route("**/api/v1/public/shares/token123", (route) =>
    route.fulfill({
      json: {
        imageUrl: png,
        title: "Teste",
        createdAt: "2026-01-01T00:00:00Z",
      },
    }),
  );
  await page.route("**/api/v1/public/shares/token123/reports", (route) =>
    route.fulfill({status: 202, json: {id: "r1", status: "pending"}}),
  );

  await page.goto("/pt-BR/s/token123");
  await expect(page.getByAltText("Teste")).toBeVisible();
  await page.getByRole("button", {name: "Denunciar"}).click();
  await expect(page.getByText("Denúncia enviada.")).toBeVisible();
});
