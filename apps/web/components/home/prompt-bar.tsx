"use client";

import {useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {useRouter} from "next/navigation";
import {Loader2, Send} from "lucide-react";

export function PromptBar({className}: {className?: string}) {
  const t = useTranslations("landing");
  const locale = useLocale();
  const router = useRouter();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    router.push(`/${locale}/studio?prompt=${encodeURIComponent(value.trim())}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={className}
      role="search"
      aria-label={t("promptPlaceholder")}
    >
      <div className="flex items-center gap-3 rounded-xl border border-foreground/10 bg-surface-raised p-2 shadow-2xl focus-within:border-accent-to">
        <label htmlFor="hero-prompt" className="sr-only">
          {t("promptPlaceholder")}
        </label>
        <input
          id="hero-prompt"
          name="prompt"
          type="text"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("promptPlaceholder")}
          className="h-14 min-w-0 flex-1 rounded-lg bg-transparent px-4 text-base text-foreground placeholder:text-muted focus-visible:outline-none sm:text-lg"
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-busy={busy}
          className="bg-accent-gradient inline-flex h-14 shrink-0 items-center gap-2 rounded-lg px-5 text-base font-semibold text-foreground disabled:opacity-50 sm:px-7 sm:text-lg"
        >
          {busy ? (
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          ) : (
            <Send className="h-5 w-5" aria-hidden />
          )}
          <span className="hidden sm:inline">
            {busy ? t("promptStatusLoading") : t("promptButton")}
          </span>
          <span className="sr-only sm:hidden">{t("promptButton")}</span>
        </button>
      </div>
    </form>
  );
}
