"use client";

import * as React from "react";
import {ChevronDown, Globe} from "lucide-react";
import {useLocale, useTranslations} from "next-intl";
import {usePathname, useRouter} from "@/i18n/navigation";
import {routing} from "@/i18n/routing";
import {cn} from "@/lib/utils";

type AppLocale = (typeof routing.locales)[number];

const LANGUAGE_NAMES: Record<AppLocale, string> = {
  "pt-BR": "Português (BR)",
  en: "English",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  ja: "日本語",
  zh: "中文",
  ru: "Русский",
  ar: "العربية",
};

const LOCALES: readonly AppLocale[] = routing.locales;

const LOCALE_COOKIE = "NEXT_LOCALE";
const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function LanguageSwitcher() {
  const t = useTranslations("language");
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const pathname = usePathname();

  const [open, setOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(
    Math.max(LOCALES.indexOf(locale), 0),
  );

  const containerRef = React.useRef<HTMLDivElement>(null);
  const buttonRef = React.useRef<HTMLButtonElement>(null);

  const listboxId = React.useId();

  const close = React.useCallback(
    (focusBack: boolean) => {
      setOpen(false);
      setActiveIndex(Math.max(LOCALES.indexOf(locale), 0));
      if (focusBack) buttonRef.current?.focus();
    },
    [locale],
  );

  function select(nextLocale: AppLocale) {
    setOpen(false);
    if (nextLocale === locale) {
      buttonRef.current?.focus();
      return;
    }

    document.cookie = `${LOCALE_COOKIE}=${nextLocale}; path=/; max-age=${LOCALE_COOKIE_MAX_AGE_SECONDS}; samesite=lax`;

    const search = window.location.search;
    const href = search ? `${pathname}${search}` : pathname;
    router.replace(href, {locale: nextLocale});
  }

  // Close on outside click.
  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        close(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open, close]);

  function handleTriggerKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (!open) {
          setOpen(true);
        } else {
          setActiveIndex((prev) => (prev + 1) % LOCALES.length);
        }
        break;
      case "ArrowUp":
        event.preventDefault();
        if (!open) {
          setOpen(true);
        } else {
          setActiveIndex((prev) => (prev - 1 + LOCALES.length) % LOCALES.length);
        }
        break;
      case "Home":
        if (open) {
          event.preventDefault();
          setActiveIndex(0);
        }
        break;
      case "End":
        if (open) {
          event.preventDefault();
          setActiveIndex(LOCALES.length - 1);
        }
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        if (!open) {
          setOpen(true);
        } else {
          select(LOCALES[activeIndex]);
        }
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        setOpen(false);
        break;
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        id={listboxId}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${listboxId}-listbox` : undefined}
        aria-label={t("selectorLabel")}
        onClick={() => (open ? close(true) : setOpen(true))}
        onKeyDown={handleTriggerKeyDown}
        className="inline-flex h-10 items-center gap-2 whitespace-nowrap rounded-full border border-foreground/10 bg-white/[0.05] px-3 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-white/[0.08] focus-visible:border-accent-to"
      >
        <Globe className="h-4 w-4 shrink-0 text-muted" aria-hidden />
        <span className="hidden sm:inline">{LANGUAGE_NAMES[locale]}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted transition-transform duration-200",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      <div
        id={`${listboxId}-listbox`}
        role="listbox"
        aria-labelledby={listboxId}
        aria-activedescendant={
          open ? `${listboxId}-option-${activeIndex}` : undefined
        }
        className={cn(
          "absolute start-0 top-full z-50 mt-2 min-w-[200px] overflow-hidden rounded-xl border border-foreground/10 bg-surface-raised shadow-2xl",
          "origin-top transition-all duration-200 ease-out",
          open
            ? "translate-y-0 opacity-100"
            : "pointer-events-none -translate-y-1 opacity-0",
        )}
      >
        {LOCALES.map((item, index) => {
          const isActive = item === locale;
          const isHighlighted = index === activeIndex;
          return (
            <button
              key={item}
              id={`${listboxId}-option-${index}`}
              type="button"
              role="option"
              aria-selected={isActive}
              tabIndex={-1}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => select(item)}
              className={cn(
                "flex w-full items-center justify-between gap-4 px-4 py-2.5 text-start text-sm transition-colors",
                "focus-visible:outline-none",
                isActive
                  ? "bg-white/[0.08] text-foreground"
                  : "text-muted hover:bg-white/[0.05] hover:text-foreground",
                isHighlighted && !isActive && "bg-white/[0.04] text-foreground",
              )}
            >
              <span>{LANGUAGE_NAMES[item]}</span>
              {isActive && (
                <span
                  className="bg-accent-gradient h-1.5 w-1.5 shrink-0 rounded-full"
                  aria-hidden
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}