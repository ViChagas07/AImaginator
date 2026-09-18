import {expect, test} from "@playwright/test";

test.describe("smoke: account & settings routes", () => {
  for (const path of ["/pt-BR/minha-conta", "/pt-BR/configuracoes"]) {
    test(`renders the app shell for ${path}`, async ({page}) => {
      await page.goto(path);
      // The header is always present, even before authentication resolves.
      await expect(
        page.getByRole("banner"),
      ).toBeVisible();
      await expect(
        page.getByRole("navigation").first(),
      ).toBeVisible();
    });
  }
});
