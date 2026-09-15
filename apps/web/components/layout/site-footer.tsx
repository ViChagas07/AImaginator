import {getTranslations} from "next-intl/server";
import {Link} from "@/i18n/navigation";

export async function SiteFooter() {
  const t = await getTranslations("common");
  const tNav = await getTranslations("nav");

  return (
    <footer className="border-t border-foreground/10 bg-surface py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 sm:px-6">
        <p className="text-sm text-muted">{t("footerNote")}</p>
        <nav className="flex gap-4" aria-label={t("brand")}>
          <Link href="/gallery" className="text-sm text-muted hover:text-foreground">
            {tNav("gallery")}
          </Link>
          <Link href="/studio" className="text-sm text-muted hover:text-foreground">
            {tNav("studio")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
