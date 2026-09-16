import type {Metadata} from "next";
import {AuthUI} from "@/components/ui/auth-ui";
import {SITE_URL} from "@/lib/constants";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/login">): Promise<Metadata> {
  const {locale} = await params;
  return {
    title: "Login",
    robots: {index: false},
    alternates: {
      canonical: `${SITE_URL}/${locale}/login`,
      languages: {
        en: `${SITE_URL}/en/login`,
        "pt-BR": `${SITE_URL}/pt-BR/login`,
      },
    },
  };
}

export default function LoginPage() {
  return <AuthUI />;
}