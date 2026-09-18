import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {SettingsPage} from "@/components/settings/settings-page";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates} from "@/lib/i18n";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/configuracoes">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("settings");
  const canonical = `${SITE_URL}/${locale}/configuracoes`;
  return {
    title: t("title"),
    description: t("subtitle"),
    robots: {index: false},
    alternates: {
      canonical,
      languages: languageAlternates("/configuracoes"),
    },
    openGraph: {
      title: t("title"),
      url: canonical,
      siteName: "AImaginator",
    },
  };
}

export default async function ConfiguracoesPage() {
  return <SettingsPage />;
}