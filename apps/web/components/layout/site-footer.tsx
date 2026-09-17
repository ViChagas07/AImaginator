import Image from "next/image";
import {getTranslations} from "next-intl/server";
import {Link} from "@/i18n/navigation";
import {NewsletterForm} from "@/components/layout/newsletter-form";
import {
  GitHubIcon,
  InstagramIcon,
  LinkedInIcon,
  XIcon,
} from "@/components/layout/social-icons";
import {SITE_NAME} from "@/lib/constants";

export async function SiteFooter() {
  const t = await getTranslations("footer");
  const tLegal = await getTranslations("legal");
  const year = new Date().getFullYear();

  const socialLinks = [
    {
      key: "instagram",
      href: "https://www.instagram.com/aimaginator",
      Icon: InstagramIcon,
    },
    {key: "x", href: "https://x.com/aimaginator", Icon: XIcon},
    {
      key: "linkedin",
      href: "https://www.linkedin.com/company/aimaginator",
      Icon: LinkedInIcon,
    },
    {key: "github", href: "https://github.com/ViChagas07/AImaginator", Icon: GitHubIcon},
  ];

  const productLinks = [
    {label: t("gallery"), href: "/gallery"},
    {label: t("howItWorks"), href: "/"},
    {label: t("pricing"), href: "/"},
    {label: t("apiDocs"), href: "/"},
  ];

  const legalLinks = [
    {label: tLegal("tabs.terms"), href: "/terms-of-use"},
    {label: tLegal("tabs.privacy"), href: "/privacy-policy"},
    {label: tLegal("tabs.cookies"), href: "/cookies"},
  ];

  return (
    <footer className="border-t border-white/[0.08] bg-canvas-raised">
      <div aria-hidden className="h-px w-full bg-accent-gradient opacity-40" />
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-3 md:gap-8">
        <div className="space-y-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground"
          >
            <Image
              src="/AImaginator_pic_transparent.png"
              alt={SITE_NAME}
              width={1412}
              height={1114}
              className="h-9 w-auto"
            />
            <span>{SITE_NAME}</span>
          </Link>
          <p className="max-w-xs text-sm text-muted">{t("tagline")}</p>
          <div className="flex gap-2">
            {socialLinks.map(({key, href, Icon}) => (
              <a
                key={key}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={t(`socialAria.${key}`)}
                className="social-icon-link flex h-9 w-9 items-center justify-center rounded-full border border-foreground/10 text-muted"
              >
                <Icon className="h-4 w-4" />
              </a>
            ))}
          </div>
        </div>

        <nav aria-label={t("productTitle")} className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
            {t("productTitle")}
          </h3>
          <ul className="space-y-2">
            {productLinks.map((link) => (
              <li key={link.label}>
                <Link
                  href={link.href}
                  className="text-sm text-muted transition-colors hover:text-foreground"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
            {t("newsletterTitle")}
          </h3>
          <p className="text-sm text-muted">{t("newsletterDescription")}</p>
          <NewsletterForm />
        </div>
      </div>

      <div className="border-t border-white/[0.08]">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="text-sm text-muted">{t("copyright", {year})}</p>
          <nav
            aria-label={tLegal("tabsLabel")}
            className="flex flex-wrap gap-x-5 gap-y-2"
          >
            {legalLinks.map((link) => (
              <Link
                key={link.label}
                href={link.href}
                className="text-sm text-muted transition-colors hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
}
