import {beforeEach, describe, expect, it, vi} from "vitest";
import {render, screen} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import messages from "../messages/pt-BR.json";
import {RandomBibleVerse} from "../components/ui/random-bible-verse";

function jsonResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as unknown as Response;
}

describe("RandomBibleVerse", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("renders the fetched verse with its reference", async () => {
    const fetched = {
      reference: "Salmos 23:1",
      text: "O Senhor é o meu pastor; nada me faltará.",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(fetched)));

    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <RandomBibleVerse />
      </NextIntlClientProvider>,
    );

    expect(await screen.findByText("— Salmos 23:1")).toBeInTheDocument();
    expect(screen.getByText(/O Senhor é o meu pastor/)).toBeInTheDocument();
  });

  it("falls back to a hardcoded verse when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <RandomBibleVerse />
      </NextIntlClientProvider>,
    );

    expect(await screen.findByText("— João 3:16")).toBeInTheDocument();
    expect(screen.getByText(/amou o mundo de tal maneira/)).toBeInTheDocument();
  });
});
