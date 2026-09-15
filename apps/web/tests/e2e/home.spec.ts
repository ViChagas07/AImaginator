import {expect, test} from "@playwright/test";

test.describe("smoke: home", () => {
  test("redirects to the default locale and renders the landing", async ({page}) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/(pt-BR|en)\/?$/);
    await expect(
      page.getByRole("heading", {level: 1, name: /Transforme palavras|Turn words/}),
    ).toBeVisible();
    await expect(page.getByRole("search")).toBeVisible();
  });

  test("exposes skip link as first focusable element", async ({page}) => {
    await page.goto("/pt-BR");
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus");
    await expect(focused).toHaveText(/Pular para o conteúdo principal|Skip to main content/);
  });

  test("renders SoftwareApplication JSON-LD", async ({page}) => {
    await page.goto("/pt-BR");
    const jsonLd = page.locator('script[type="application/ld+json"]');
    const content = await jsonLd.first().textContent();
    expect(content).toContain('"@type":"SoftwareApplication"');
  });
});
