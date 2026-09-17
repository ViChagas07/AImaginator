import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {AuthUI} from "@/components/ui/auth-ui";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates} from "@/lib/i18n";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/login">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("auth");
  const canonical = `${SITE_URL}/${locale}/login`;
  return {
    title: t("signIn.title"),
    robots: {index: false},
    alternates: {
      canonical,
      languages: languageAlternates("/login"),
    },
  };
}

export default function LoginPage() {
  return <AuthUI />;
}