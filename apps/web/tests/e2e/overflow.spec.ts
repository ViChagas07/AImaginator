import {expect, test} from "@playwright/test";

const locales = ["pt-BR", "en", "es", "fr", "de", "it", "ja", "zh", "ko", "ru", "ar"];

test.describe("overflow horizontal em 360px", () => {
  for (const locale of locales) {
    for (const path of ["", "/gallery"]) {
      test(`${locale} ${path || "/"}`, async ({page}) => {
        await page.setViewportSize({width: 360, height: 800});
        await page.goto(`/${locale}${path}`);
        await page.waitForLoadState("domcontentloaded");
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        );
        expect(overflow, `${locale}${path}`).toBeLessThanOrEqual(1);
      });
    }
  }
});
