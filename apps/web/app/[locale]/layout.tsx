import type {Metadata} from "next";
import {Geist, Geist_Mono} from "next/font/google";
import {hasLocale, NextIntlClientProvider} from "next-intl";
import {getTranslations} from "next-intl/server";
import {notFound} from "next/navigation";
import {routing} from "@/i18n/routing";
import {SiteHeader} from "@/components/layout/site-header";
import {SiteFooter} from "@/components/layout/site-footer";
import {SITE_URL} from "@/lib/constants";
import "../globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const {locale} = await params;
  return {
    metadataBase: new URL(SITE_URL),
    alternates: {
      languages: {
        en: `${SITE_URL}/en`,
        "pt-BR": `${SITE_URL}/pt-BR`,
      },
    },
    title: {
      default: "AImaginator",
      template: "%s — AImaginator",
    },
    description:
      locale === "pt-BR"
        ? "AImaginator gera e edita imagens com IA a partir de prompts em linguagem natural."
        : "AImaginator generates and edits images with AI from natural-language prompts.",
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({locale}));
}

export default async function RootLayout({
  children,
  params,
}: LayoutProps<"/[locale]">) {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  const t = await getTranslations("common");

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas text-foreground">
        <NextIntlClientProvider>
          <a
            href="#main"
            className="sr-only z-50 bg-surface-raised px-4 py-2 text-sm text-foreground focus:not-sr-only focus:absolute"
          >
            {t("skipLink")}
          </a>
          <SiteHeader />
          <main id="main" className="flex-1">
            {children}
          </main>
          <SiteFooter />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
