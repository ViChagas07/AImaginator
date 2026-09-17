"use client";

import {useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {useRouter} from "next/navigation";
import {Loader2, Plus, Send, X} from "lucide-react";
import {useGenerationStore} from "@/stores/generation";

export function PromptBar({className}: {className?: string}) {
  const t = useTranslations("landing");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const gen = useGenerationStore();
  const fileRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const imageBase64 = gen.imageBase64;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
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

  return (
    <form
      onSubmit={handleSubmit}
      className={className}
      role="search"
      aria-label={t("promptPlaceholder")}
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
          aria-label={tCommon("attachImage")}
          title={tCommon("attachImage")}
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-foreground/10 text-muted transition-colors hover:text-foreground focus-visible:border-accent-to focus-visible:outline-none"
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
              aria-label={tCommon("removeImage")}
              title={tCommon("removeImage")}
              className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-foreground/10 bg-surface text-muted hover:text-foreground focus-visible:outline-none"
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
          placeholder={t("promptPlaceholder")}
          className="h-14 min-w-0 flex-1 rounded-lg bg-transparent px-4 text-base text-foreground placeholder:text-muted focus-visible:outline-none sm:text-lg"
        />
        <button
          type="submit"
          disabled={busy || (!value.trim() && !imageBase64)}
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
