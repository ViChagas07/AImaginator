import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {LegalPageTabs} from "@/components/legal/legal-page-tabs";
import {PrivacyPolicySection as LegalSection} from "@/components/legal/privacy-policy-section";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates, openGraphLocale} from "@/lib/i18n";

const SECTION_COUNT = 10;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/terms-of-use">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("legal");
  const canonical = `${SITE_URL}/${locale}/terms-of-use`;
  return {
    title: t("terms.title"),
    description: t("terms.description"),
    alternates: {
      canonical,
      languages: languageAlternates("/terms-of-use"),
    },
    openGraph: {
      type: "website",
      url: canonical,
      title: t("terms.title"),
      description: t("terms.description"),
      siteName: "AImaginator",
      locale: openGraphLocale(locale),
    },
    twitter: {
      card: "summary",
      title: t("terms.title"),
      description: t("terms.description"),
    },
  };
}

export default async function TermsOfUsePage({
  params,
}: PageProps<"/[locale]/terms-of-use">) {
  await params;
  const t = await getTranslations("legal");

  const sections = Array.from({length: SECTION_COUNT}, (_, i) => ({
    title: t(`terms.sections.${i}.title`),
    body: t(`terms.sections.${i}.body`),
  }));

  return (
    <div>
      <LegalPageTabs active="terms" />
      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6 sm:py-20">
        <header className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-lilac">
            {t("terms.kicker")}
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {t("terms.title")}
          </h1>
          <p className="mt-4 text-sm text-muted">{t("terms.updated")}</p>
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
