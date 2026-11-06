import {describe, expect, it} from "vitest";
import {
  scrubSentryBreadcrumb,
  scrubSentryEvent,
  scrubText,
} from "../lib/sentry-scrub";

describe("sentry scrubbing (frontend)", () => {
  it("removes email, IP, tokens and signed URLs from text", () => {
    const text =
      "user@example.com 10.1.2.3 Bearer abc.def.ghi " +
      "https://bucket/x?X-Amz-Signature=deadbeef";
    const scrubbed = scrubText(text);
    expect(scrubbed).not.toContain("user@example.com");
    expect(scrubbed).not.toContain("10.1.2.3");
    expect(scrubbed).not.toContain("abc.def.ghi");
    expect(scrubbed).not.toContain("deadbeef");
  });

  it("scrubs prompt in event, extra, exception and breadcrumbs", () => {
    const event = {
      message: "prompt=segredo user@example.com",
      user: {email: "user@example.com"},
      request: {
        data: {prompt: "segredo"},
        cookies: {session: "x"},
        headers: {Authorization: "Bearer token"},
      },
      exception: {values: [{value: "prompt=segredo"}]},
      breadcrumbs: {values: [{message: "prompt=segredo", data: {prompt: "segredo"}}]},
      extra: {prompt: "segredo", object_key: "generations/1/original.png"},
      tags: {prompt: "segredo"},
    };
    const scrubbed = scrubSentryEvent(event);
    const serialized = JSON.stringify(scrubbed);
    expect(serialized).not.toContain("segredo");
    expect(serialized).not.toContain("user@example.com");
    expect(serialized).not.toContain("generations/1/original.png");
    expect(scrubbed.user).toBeUndefined();
  });

  it("scrubs breadcrumb data", () => {
    const breadcrumb = scrubSentryBreadcrumb({
      message: "prompt=segredo",
      data: {url: "https://x?X-Amz-Signature=abc"},
    });
    expect(JSON.stringify(breadcrumb)).not.toContain("segredo");
    expect(JSON.stringify(breadcrumb)).not.toContain("abc");
  });
});
