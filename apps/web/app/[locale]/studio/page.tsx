import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {StudioApp} from "@/components/studio/studio-app";
import {SITE_URL} from "@/lib/constants";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/studio">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("studio");
  const canonical = `${SITE_URL}/${locale}/studio`;
  return {
    title: t("title"),
    description: t("loginRequired"),
    robots: {index: false},
    alternates: {
      canonical,
      languages: {
        en: `${SITE_URL}/en/studio`,
        "pt-BR": `${SITE_URL}/pt-BR/studio`,
      },
    },
    openGraph: {
      title: t("title"),
      url: canonical,
      siteName: "AImaginator",
    },
  };
}

export default async function StudioPage({
  searchParams,
}: PageProps<"/[locale]/studio">) {
  const {prompt} = await searchParams;
  const t = await getTranslations("studio");
  const initialPrompt =
    typeof prompt === "string" && prompt.length > 0 ? prompt : undefined;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="mb-8 text-3xl font-semibold tracking-tight text-foreground">
        {t("title")}
      </h1>
      <StudioApp initialPrompt={initialPrompt} />
    </div>
  );
}
