import type {Metadata} from "next";
import Image from "next/image";
import {getTranslations} from "next-intl/server";
import {ImageStreamHero} from "@/components/ui/image-stream-hero";
import {PromptBar} from "@/components/home/prompt-bar";
import {StepsSection} from "@/components/home/steps-section";
import {ExamplesGrid} from "@/components/home/examples-grid";
import {FaqSection} from "@/components/home/faq-section";
import {SITE_URL} from "@/lib/constants";
import {languageAlternates, openGraphLocale} from "@/lib/i18n";

const HERO_IMAGES = [
  {src: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=400&q=60", alt: ""},
  {src: "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=400&q=60", alt: ""},
  {src: "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=400&q=60", alt: ""},
  {src: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=400&q=60", alt: ""},
  {src: "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=400&q=60", alt: ""},
  {src: "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=400&q=60", alt: ""},
];

export async function generateMetadata({
  params,
}: PageProps<"/[locale]">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("landing");
  const canonical = `${SITE_URL}/${locale}`;
  return {
    title: t("headline"),
    description: t("subheadline"),
    alternates: {
      canonical,
      languages: languageAlternates("/"),
    },
    openGraph: {
      type: "website",
      url: canonical,
      title: t("headline"),
      description: t("subheadline"),
      siteName: "AImaginator",
      locale: openGraphLocale(locale),
    },
    twitter: {
      card: "summary_large_image",
      title: t("headline"),
      description: t("subheadline"),
    },
  };
}

export default async function LandingPage({params}: PageProps<"/[locale]">) {
  await params;
  const t = await getTranslations("landing");

  const softwareAppJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AImaginator",
    applicationCategory: "DesignApplication",
    operatingSystem: "Web",
    url: SITE_URL,
    description: t("subheadline"),
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
  };

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [0, 1, 2, 3].map((i) => ({
      "@type": "Question",
      name: t(`faq.${i}.question`),
      acceptedAnswer: {
        "@type": "Answer",
        text: t(`faq.${i}.answer`),
      },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{__html: JSON.stringify(softwareAppJsonLd)}}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{__html: JSON.stringify(faqJsonLd)}}
      />
      <section aria-label={t("headline")}>
        <ImageStreamHero
          images={HERO_IMAGES}
          className="h-[420px] sm:h-[520px] lg:h-[640px]"
        >
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-canvas/60 px-4 text-center">
            <Image
              src="/AImaginator_pic_transparent.png"
              alt={t("logoAlt")}
              width={1412}
              height={1114}
              priority
              className="logo-dark animate-hero-enter h-auto w-[150px] drop-shadow-[0_10px_32px_rgba(76,111,255,0.35)] motion-reduce:animate-none sm:w-[190px] lg:w-[220px]"
            />
            <Image
              src="/AImaginator_black-transparent.png"
              alt={t("logoAlt")}
              width={1412}
              height={1114}
              priority
              className="logo-light animate-hero-enter h-auto w-[150px] drop-shadow-[0_10px_32px_rgba(76,111,255,0.35)] motion-reduce:animate-none sm:w-[190px] lg:w-[220px]"
            />
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              {t("headline")}
            </h1>
            <p className="max-w-2xl text-base leading-relaxed text-foreground/90 sm:text-lg">
              {t("subheadline")}
            </p>
          </div>
        </ImageStreamHero>
        <div className="relative z-10 mx-auto -mt-4 max-w-4xl px-2 sm:px-6">
          <PromptBar />
        </div>
      </section>
      <StepsSection />
      <ExamplesGrid />
      <FaqSection />
    </>
  );
}
