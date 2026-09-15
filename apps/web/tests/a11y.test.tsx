import {describe, expect, it} from "vitest";
import {render} from "@testing-library/react";
import axe from "axe-core";
import {NextIntlClientProvider} from "next-intl";
import messages from "../messages/en.json";
import {PromptBar} from "../components/home/prompt-bar";

describe("landing accessibility", () => {
  it("prompt bar has no accessibility violations", async () => {
    const {container} = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <main>
          <h1>Turn words into images.</h1>
          <PromptBar />
        </main>
      </NextIntlClientProvider>,
    );

    const results = await axe.run(container, {
      rules: {
        // jsdom não calcula layout real; contraste é validado no CSS/tokens.
        "color-contrast": {enabled: false},
      },
    });
    expect(results.violations).toEqual([]);
  });
});
