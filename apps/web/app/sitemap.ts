import type {MetadataRoute} from "next";
import {routing} from "@/i18n/routing";
import {SITE_URL} from "@/lib/constants";

const PATHS = ["/", "/gallery", "/privacy-policy", "/terms-of-use", "/cookies"] as const;

function localizedUrl(locale: string, path: string) {
  return `${SITE_URL}/${locale}${path === "/" ? "" : path}`;
}

export default function sitemap(): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = [];

  for (const path of PATHS) {
    for (const locale of routing.locales) {
      entries.push({
        url: localizedUrl(locale, path),
        lastModified: new Date(),
        changeFrequency: path === "/" ? "weekly" : "daily",
        priority: path === "/" ? 1 : 0.8,
        alternates: {
          languages: Object.fromEntries([
            ...routing.locales.map(
              (altLocale) => [altLocale, localizedUrl(altLocale, path)] as const,
            ),
            ["x-default", localizedUrl(routing.defaultLocale, path)] as const,
          ]),
        },
      });
    }
  }

  return entries;
}