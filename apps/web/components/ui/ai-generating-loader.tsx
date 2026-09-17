"use client";

import {useTranslations} from "next-intl";
import {cn} from "@/lib/utils";

export type AIGeneratingLoaderProps = {
  className?: string;
  label?: string;
  ariaLabel?: string;
};

const LETTER_STAGGER_SECONDS = 0.1;

export function AIGeneratingLoader({
  className,
  label,
  ariaLabel,
}: AIGeneratingLoaderProps) {
  const t = useTranslations("loader");
  const word = label ?? t("generating");
  const accessibleLabel = ariaLabel ?? t("ariaLabel");
  const letters = Array.from(word);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={accessibleLabel}
      className={cn(
        "relative flex h-32 w-32 items-center justify-center sm:h-40 sm:w-40 md:h-44 md:w-44",
        className,
      )}
    >
      <span aria-hidden className="aigl-spinner" />
      <span
        aria-hidden
        className="relative z-10 flex items-center justify-center px-4 text-base font-light tracking-wide text-foreground sm:text-lg"
      >
        {letters.map((char, index) => (
          <span
            key={`${index}-${char}`}
            className="aigl-letter"
            style={{animationDelay: `${index * LETTER_STAGGER_SECONDS}s`}}
          >
            {char === " " ? "\u00A0" : char}
          </span>
        ))}
      </span>
    </div>
  );
}

export default AIGeneratingLoader;
