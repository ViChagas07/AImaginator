import {routing} from "@/i18n/routing";
import {SITE_URL} from "@/lib/constants";

export function languageAlternates(pathname = "/") {
  const suffix = pathname === "/" ? "" : pathname;
  const entries = routing.locales.map(
    (locale): [string, string] => [locale, `${SITE_URL}/${locale}${suffix}`],
  );
  return Object.fromEntries([
    ...entries,
    ["x-default", `${SITE_URL}/${routing.defaultLocale}${suffix}`],
  ]);
}

const OPEN_GRAPH_LOCALES: Record<string, string> = {
  en: "en_US",
  "pt-BR": "pt_BR",
  es: "es_ES",
  fr: "fr_FR",
  de: "de_DE",
  ja: "ja_JP",
  zh: "zh_CN",
  ru: "ru_RU",
  ar: "ar_AR",
};

export function openGraphLocale(locale: string): string {
  return OPEN_GRAPH_LOCALES[locale] ?? locale.replace("-", "_");
}