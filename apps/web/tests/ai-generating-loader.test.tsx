import {describe, expect, it} from "vitest";
import {render, screen} from "@testing-library/react";
import axe from "axe-core";
import {NextIntlClientProvider} from "next-intl";
import messages from "../messages/en.json";
import {AIGeneratingLoader} from "../components/ui/ai-generating-loader";

describe("AIGeneratingLoader", () => {
  it("is accessible and announces the generating state", async () => {
    const {container} = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <AIGeneratingLoader />
      </NextIntlClientProvider>,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute(
      "aria-label",
      "Generating image, please wait",
    );

    const results = await axe.run(container, {
      rules: {"color-contrast": {enabled: false}},
    });
    expect(results.violations).toEqual([]);
  });

  it("renders the translated word letter by letter", () => {
    const {container} = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <AIGeneratingLoader />
      </NextIntlClientProvider>,
    );

    expect(container.textContent).toContain("Generating");
  });

  it("allows overriding the label and aria-label", () => {
    const {container} = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <AIGeneratingLoader label="Carregando" ariaLabel="Carregando imagem" />
      </NextIntlClientProvider>,
    );

    expect(container.textContent).toContain("Carregando");
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      "Carregando imagem",
    );
  });
});
