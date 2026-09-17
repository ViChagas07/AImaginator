import {routing} from "@/i18n/routing";
import {SITE_URL} from "@/lib/constants";

export function languageAlternates(pathname = "/") {
  const suffix = pathname === "/" ? "" : pathname;
  return Object.fromEntries(
    routing.locales.map((locale) => [locale, `${SITE_URL}/${locale}${suffix}`]),
  );
}

const OPEN_GRAPH_LOCALES: Record<string, string> = {
  en: "en_US",
  "pt-BR": "pt_BR",
  es: "es_ES",
  fr: "fr_FR",
  de: "de_DE",
  it: "it_IT",
};

export function openGraphLocale(locale: string): string {
  return OPEN_GRAPH_LOCALES[locale] ?? locale.replace("-", "_");
}
