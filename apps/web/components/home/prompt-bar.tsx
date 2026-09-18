"use client";

import {useEffect, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {useRouter} from "next/navigation";
import {Loader2, Plus, Send, Timer, X} from "lucide-react";
import {useGenerationStore} from "@/stores/generation";
import {usePromptQuotaStore} from "@/stores/prompt-quota";
import {useCountdown} from "@/lib/use-countdown";
import {cn} from "@/lib/utils";

function formatCountdown(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function PromptBar({className}: {className?: string}) {
  const t = useTranslations("landing");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const gen = useGenerationStore();
  const quota = usePromptQuotaStore();
  const fileRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const imageBase64 = gen.imageBase64;

  useEffect(() => {
    void quota.fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exhausted = quota.loaded && quota.chancesRemaining === 0;
  const countdown = useCountdown(exhausted ? quota.nextAvailableAt : null);

  // Quando o countdown zera, revalida com o backend antes de liberar a barra
  // (evita manipulação do relógio do cliente).
  const revalidatedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!exhausted) {
      revalidatedFor.current = null;
      return;
    }
    if (countdown === 0 && revalidatedFor.current !== quota.nextAvailableAt) {
      revalidatedFor.current = quota.nextAvailableAt;
      void quota.refresh();
    }
  }, [countdown, exhausted, quota]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (exhausted) return;
    if (!value.trim() && !imageBase64) return;
    setBusy(true);
    router.push(`/${locale}/studio?prompt=${encodeURIComponent(value.trim())}`);
  }

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => gen.setImage(reader.result as string);
    reader.readAsDataURL(file);
    event.target.value = "";
  }

  const inputDisabled = exhausted || busy || (!value.trim() && !imageBase64);

  return (
    <div className={cn("relative", className)}>
      <form
        onSubmit={handleSubmit}
        role="search"
        aria-label={t("promptPlaceholder")}
        className={cn(exhausted && "pointer-events-none select-none blur-sm")}
      >
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleFile}
          className="hidden"
          aria-label={tCommon("attachImage")}
          tabIndex={-1}
        />
        <div className="flex items-center gap-3 rounded-xl border border-foreground/10 bg-surface-raised p-2 shadow-2xl focus-within:border-accent-to">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={exhausted}
            aria-label={tCommon("attachImage")}
            title={tCommon("attachImage")}
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-foreground/10 text-muted transition-colors hover:text-foreground focus-visible:border-accent-to focus-visible:outline-none disabled:opacity-50"
          >
            <Plus className="h-6 w-6" aria-hidden />
          </button>
          {imageBase64 ? (
            <div className="relative shrink-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageBase64}
                alt={tCommon("attachedImageAlt")}
                className="h-14 w-14 rounded-lg border border-foreground/10 object-cover"
              />
              <button
                type="button"
                onClick={() => gen.setImage(undefined)}
                disabled={exhausted}
                aria-label={tCommon("removeImage")}
                title={tCommon("removeImage")}
                className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-foreground/10 bg-surface text-muted hover:text-foreground focus-visible:outline-none disabled:opacity-50"
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </div>
          ) : null}
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
            disabled={exhausted}
            placeholder={t("promptPlaceholder")}
            className="h-14 min-w-0 flex-1 rounded-lg bg-transparent px-4 text-base text-foreground placeholder:text-muted focus-visible:outline-none disabled:opacity-50 sm:text-lg"
          />
          <button
            type="submit"
            disabled={inputDisabled}
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

      <div
        role="status"
        aria-live="polite"
        className="mt-3 flex items-center justify-center gap-2 text-sm text-muted"
      >
        {quota.loaded ? (
          <>
            <span>
              {t("quotaAvailable", {
                remaining: quota.chancesRemaining,
                total: quota.chancesTotal,
              })}
            </span>
            {exhausted ? (
              <>
                <span aria-hidden="true">·</span>
                <Timer className="h-4 w-4" aria-hidden />
                <span>{t("quotaReloadsIn")}</span>
                <span className="font-mono tabular-nums">{formatCountdown(countdown)}</span>
              </>
            ) : null}
          </>
        ) : (
          <span>{t("quotaLoading")}</span>
        )}
      </div>
    </div>
  );
}
