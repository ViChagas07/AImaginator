import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {LegalPageTabs} from "@/components/legal/legal-page-tabs";
import {PrivacyPolicySection} from "@/components/legal/privacy-policy-section";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates, openGraphLocale} from "@/lib/i18n";

const SECTION_COUNT = 10;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/privacy-policy">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("legal");
  const canonical = `${SITE_URL}/${locale}/privacy-policy`;
  return {
    title: t("privacy.title"),
    description: t("privacy.description"),
    alternates: {
      canonical,
      languages: languageAlternates("/privacy-policy"),
    },
    openGraph: {
      type: "website",
      url: canonical,
      title: t("privacy.title"),
      description: t("privacy.description"),
      siteName: "AImaginator",
      locale: openGraphLocale(locale),
    },
    twitter: {
      card: "summary",
      title: t("privacy.title"),
      description: t("privacy.description"),
    },
  };
}

export default async function PrivacyPolicyPage({
  params,
}: PageProps<"/[locale]/privacy-policy">) {
  await params;
  const t = await getTranslations("legal");

  const sections = Array.from({length: SECTION_COUNT}, (_, i) => ({
    title: t(`privacy.sections.${i}.title`),
    body: t(`privacy.sections.${i}.body`),
  }));

  return (
    <div>
      <LegalPageTabs active="privacy" />
      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6 sm:py-20">
        <header className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-lilac">
            {t("privacy.kicker")}
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {t("privacy.title")}
          </h1>
          <p className="mt-4 text-sm text-muted">{t("privacy.updated")}</p>
        </header>
        <article>
          {sections.map((section) => (
            <PrivacyPolicySection
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
