import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {LegalPageTabs} from "@/components/legal/legal-page-tabs";
import {PrivacyPolicySection as LegalSection} from "@/components/legal/privacy-policy-section";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates, openGraphLocale} from "@/lib/i18n";

const SECTION_COUNT = 7;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/cookies">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("legal");
  const canonical = `${SITE_URL}/${locale}/cookies`;
  return {
    title: t("cookies.title"),
    description: t("cookies.description"),
    alternates: {
      canonical,
      languages: languageAlternates("/cookies"),
    },
    openGraph: {
      type: "website",
      url: canonical,
      title: t("cookies.title"),
      description: t("cookies.description"),
      siteName: "AImaginator",
      locale: openGraphLocale(locale),
    },
    twitter: {
      card: "summary",
      title: t("cookies.title"),
      description: t("cookies.description"),
    },
  };
}

export default async function CookiesPage({
  params,
}: PageProps<"/[locale]/cookies">) {
  await params;
  const t = await getTranslations("legal");

  const sections = Array.from({length: SECTION_COUNT}, (_, i) => ({
    title: t(`cookies.sections.${i}.title`),
    body: t(`cookies.sections.${i}.body`),
  }));

  return (
    <div>
      <LegalPageTabs active="cookies" />
      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6 sm:py-20">
        <header className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-lilac">
            {t("cookies.kicker")}
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {t("cookies.title")}
          </h1>
          <p className="mt-4 text-sm text-muted">{t("cookies.updated")}</p>
        </header>
        <article>
          {sections.map((section) => (
            <LegalSection
              key={section.title}
              title={section.title}
              body={section.body}
            />
          ))}
        </article>
      </div>
    </div>
  );
}
