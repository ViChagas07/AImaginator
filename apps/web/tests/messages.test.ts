import {describe, expect, it} from "vitest";
import pt from "../messages/pt-BR.json";
import en from "../messages/en.json";
import es from "../messages/es.json";
import fr from "../messages/fr.json";
import de from "../messages/de.json";
import itMessages from "../messages/it.json";
import ja from "../messages/ja.json";
import zh from "../messages/zh.json";
import koMessages from "../messages/ko.json";
import ru from "../messages/ru.json";
import ar from "../messages/ar.json";
import review from "../messages/_review.json";

const ALL = {"pt-BR": pt, en, es, fr, de, it: itMessages, ja, zh, ko: koMessages, ru, ar} as const;

function flatten(node: unknown, prefix = ""): Record<string, string> {
  if (typeof node === "string") return {[prefix]: node};
  if (Array.isArray(node)) {
    return node.reduce<Record<string, string>>((acc, item, index) => {
      Object.assign(acc, flatten(item, `${prefix}[${index}]`));
      return acc;
    }, {});
  }
  if (typeof node === "object" && node !== null) {
    return Object.entries(node).reduce<Record<string, string>>((acc, [key, value]) => {
      Object.assign(acc, flatten(value, prefix ? `${prefix}.${key}` : key));
      return acc;
    }, {});
  }
  return {};
}

const reference = flatten(pt);
const placeholders = (value: string) => [...value.matchAll(/\{[^}]+\}/g)].map((m) => m[0]).sort();

describe("i18n messages", () => {
  it("has the same key set in all 11 locales", () => {
    for (const [locale, messages] of Object.entries(ALL)) {
      const flat = flatten(messages);
      expect(Object.keys(flat).sort(), locale).toEqual(Object.keys(reference).sort());
      for (const [key, value] of Object.entries(flat)) {
        expect(value.trim().length, `${locale}/${key}`).toBeGreaterThan(0);
        expect(placeholders(value), `${locale}/${key}`).toEqual(placeholders(reference[key]));
      }
    }
  });

  it("has a review status file for all 11 locales", () => {
    const locales = Object.keys(ALL).sort();
    expect(Object.keys(review).sort()).toEqual(locales);
    for (const [locale, entry] of Object.entries(review)) {
      expect(["pending", "reviewed"], locale).toContain(entry.status);
      expect(entry).toHaveProperty("reviewer");
      expect(entry).toHaveProperty("date");
    }
  });

  it("includes Italian and Korean with real content", () => {
    const itFlat = flatten(itMessages);
    const koFlat = flatten(koMessages);
    expect(itFlat["studio.modeGenerate"]).not.toBe(reference["studio.modeGenerate"]);
    expect(koFlat["studio.modeGenerate"]).not.toBe(reference["studio.modeGenerate"]);
    expect(itFlat["language.selectorLabel"]).toBeTruthy();
    expect(koFlat["language.selectorLabel"]).toBeTruthy();
  });
});
