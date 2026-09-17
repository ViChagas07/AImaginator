import {describe, expect, it} from "vitest";
import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import {NextIntlClientProvider} from "next-intl";
import messages from "../messages/en.json";
import {NewsletterForm} from "../components/layout/newsletter-form";
import {PrivacyPolicySection} from "../components/legal/privacy-policy-section";

describe("footer and legal accessibility", () => {
  it("newsletter form has no accessibility violations", async () => {
    const {container} = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <NewsletterForm />
      </NextIntlClientProvider>,
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": {enabled: false},
      },
    });
    expect(results.violations).toEqual([]);
  });

  it("newsletter form confirms a submitted email", async () => {
    const user = userEvent.setup();
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <NewsletterForm />
      </NextIntlClientProvider>,
    );

    await user.type(screen.getByLabelText("Email address"), "user@example.com");
    await user.click(screen.getByRole("button", {name: "Subscribe"}));

    expect(screen.getByText(/Subscription confirmed/)).toBeInTheDocument();
  });

  it("privacy policy section renders its heading and body", () => {
    render(
      <PrivacyPolicySection
        title="What are cookies?"
        body="Cookies are small text files stored in your browser."
      />,
    );

    expect(
      screen.getByRole("heading", {level: 2, name: "What are cookies?"}),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Cookies are small text files stored in your browser."),
    ).toBeInTheDocument();
  });
});
