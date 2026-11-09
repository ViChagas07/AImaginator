import {describe, expect, it} from "vitest";

import {pseudoLocalize} from "../i18n/pseudo";

describe("pseudo-localizacao", () => {
  it("marca strings preservando placeholders", () => {
    const value = pseudoLocalize({
      title: "Olá {name}",
      nested: {count: "3 créditos"},
    });
    expect(value.title).toBe("⟦Olá {name}⟧");
    expect(value.nested.count).toBe("⟦3 créditos⟧");
  });
});
