/** Pseudo-localizacao opt-in em development para detectar texto fixo/overflow. */

export function pseudoLocalize<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => pseudoLocalize(item)) as T;
  }
  if (value && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      result[key] = pseudoLocalize(item);
    }
    return result as T;
  }
  if (typeof value === "string") {
    return `⟦${value}⟧` as T;
  }
  return value;
}

export function pseudoEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_PSEUDO_LOCALIZATION === "1"
  );
}
