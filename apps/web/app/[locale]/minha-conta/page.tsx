import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {AccountPage} from "@/components/account/account-page";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates} from "@/lib/i18n";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/minha-conta">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("account");
  const canonical = `${SITE_URL}/${locale}/minha-conta`;
  return {
    title: t("title"),
    description: t("subtitle"),
    robots: {index: false},
    alternates: {
      canonical,
      languages: languageAlternates("/minha-conta"),
    },
    openGraph: {
      title: t("title"),
      url: canonical,
      siteName: "AImaginator",
    },
  };
}

export default async function MinhaContaPage() {
  return <AccountPage />;
}