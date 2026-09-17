import {getTranslations} from "next-intl/server";
import {Link} from "@/i18n/navigation";
import {cn} from "@/lib/utils";

export type LegalTabId = "terms" | "privacy" | "cookies";

const TABS: {id: LegalTabId; href: string}[] = [
  {id: "terms", href: "/terms-of-use"},
  {id: "privacy", href: "/privacy-policy"},
  {id: "cookies", href: "/cookies"},
];

export async function LegalPageTabs({active}: {active: LegalTabId}) {
  const t = await getTranslations("legal");

  return (
    <nav
      aria-label={t("tabsLabel")}
      className="border-b border-white/[0.08] bg-white/[0.03]"
    >
      <div className="mx-auto flex max-w-6xl gap-6 overflow-x-auto px-4 sm:px-6">
        {TABS.map((tab) => {
          const isActive = tab.id === active;
          return (
            <Link
              key={tab.id}
              href={tab.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "relative shrink-0 py-3.5 text-sm font-medium transition-colors",
                isActive ? "text-foreground" : "text-muted hover:text-foreground",
              )}
            >
              {t(`tabs.${tab.id}`)}
              <span
                aria-hidden
                className={cn(
                  "bg-accent-gradient absolute inset-x-0 bottom-0 h-0.5 rounded-full",
                  isActive ? "opacity-100" : "opacity-0",
                )}
              />
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
