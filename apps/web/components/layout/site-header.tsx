import {getTranslations} from "next-intl/server";
import {Link} from "@/i18n/navigation";
import {AuthButton} from "@/components/layout/auth-button";

export async function SiteHeader() {
  const t = await getTranslations("nav");
  const tCommon = await getTranslations("common");

  return (
    <header className="border-b border-foreground/10 bg-canvas">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link
          href="/"
          className="text-lg font-semibold tracking-tight text-foreground"
        >
          {tCommon("brand")}
        </Link>
        <nav
          aria-label={tCommon("brand")}
          className="ml-auto flex items-center gap-2"
        >
          <Link
            href="/gallery"
            className="rounded-md px-3 py-2 text-sm text-muted hover:text-foreground"
          >
            {t("gallery")}
          </Link>
          <Link
            href="/studio"
            className="rounded-md px-3 py-2 text-sm text-muted hover:text-foreground"
          >
            {t("studio")}
          </Link>
          <AuthButton />
        </nav>
      </div>
    </header>
  );
}
