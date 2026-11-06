import type {Metadata} from "next";
import {
  Geist,
  Geist_Mono,
  Noto_Sans_Arabic,
  Noto_Sans_JP,
  Noto_Sans_KR,
  Noto_Sans_SC,
} from "next/font/google";
import {hasLocale, NextIntlClientProvider} from "next-intl";
import {getTranslations} from "next-intl/server";
import {notFound} from "next/navigation";
import {routing} from "@/i18n/routing";
import {SiteHeader} from "@/components/layout/site-header";
import {SiteFooter} from "@/components/layout/site-footer";
import {ToastProvider} from "@/components/ui/toast";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates, openGraphLocale} from "@/lib/i18n";
import "../globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const notoJp = Noto_Sans_JP({
  variable: "--font-noto-jp",
  display: "swap",
  preload: false,
});

const notoSc = Noto_Sans_SC({
  variable: "--font-noto-sc",
  display: "swap",
  preload: false,
});

const notoKr = Noto_Sans_KR({
  variable: "--font-noto-kr",
  display: "swap",
  preload: false,
});

const notoArabic = Noto_Sans_Arabic({
  variable: "--font-noto-arabic",
  subsets: ["arabic", "latin"],
  display: "swap",
  preload: false,
});

export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("landing");
  const title = `AImaginator \u2014 ${t("headline")}`;
  const description = t("subheadline");
  return {
    metadataBase: new URL(SITE_URL),
    alternates: {
      languages: languageAlternates("/"),
      canonical: `/${locale}`,
    },
    title: {
      default: title,
      template: "%s \u2014 AImaginator",
    },
    description,
    openGraph: {
      type: "website",
      locale: openGraphLocale(locale),
      url: `/${locale}`,
      siteName: "AImaginator",
      title,
      description,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
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
  const isRtl = locale === "ar";

  return (
    <html
      lang={locale}
      dir={isRtl ? "rtl" : "ltr"}
      data-scroll-behavior="smooth"
      className={`${geistSans.variable} ${geistMono.variable} ${notoJp.variable} ${notoSc.variable} ${notoKr.variable} ${notoArabic.variable} h-full antialiased`}
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
          <ToastProvider />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
