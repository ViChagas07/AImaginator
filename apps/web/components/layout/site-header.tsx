import Image from "next/image";
import {getTranslations} from "next-intl/server";
import {Link} from "@/i18n/navigation";
import {AuthButton} from "@/components/layout/auth-button";
import {LanguageSwitcher} from "@/components/layout/language-switcher";

export async function SiteHeader() {
  const t = await getTranslations("nav");
  const tCommon = await getTranslations("common");

  return (
    <header className="border-b border-foreground/10 bg-canvas">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground"
          >
            <Image
              src="/AImaginator_pic_transparent.png"
              alt={tCommon("brand")}
              width={476}
              height={317}
              priority
              className="h-10 w-auto logo-dark"
            />
            <Image
              src="/AImaginator_black-transparent.png"
              alt={tCommon("brand")}
              width={476}
              height={317}
              priority
              className="h-10 w-auto logo-light"
            />
          </Link>
          <LanguageSwitcher />
        </div>
        <nav
          aria-label={tCommon("brand")}
          className="ms-auto flex items-center gap-2"
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
