import Image from "next/image";
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
          className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground"
        >
          <Image
            src="/AImaginator_pic_transparent.png"
            alt=""
            width={1412}
            height={1114}
            priority
            className="h-9 w-auto"
          />
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
