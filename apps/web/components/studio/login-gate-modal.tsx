"use client";

import {useTranslations} from "next-intl";
import {Link} from "@/i18n/navigation";

export function LoginGateModal({
  open,
  onDismiss,
}: {
  open: boolean;
  onDismiss: () => void;
}) {
  const t = useTranslations("studio");
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("saveArtTitle")}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        aria-label={t("saveArtLater")}
        onClick={onDismiss}
        className="absolute inset-0 cursor-default bg-black/50"
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border border-foreground/10 bg-surface p-6 text-center shadow-2xl">
        <h2 className="text-xl font-semibold text-foreground">{t("saveArtTitle")}</h2>
        <p className="mt-2 text-sm text-muted">{t("saveArtBody")}</p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <Link
            href="/login"
            className="bg-accent-gradient inline-flex items-center justify-center rounded-md px-5 py-2.5 text-sm font-semibold text-foreground"
          >
            {t("saveArtCta")}
          </Link>
          <button
            type="button"
            onClick={onDismiss}
            className="inline-flex items-center justify-center rounded-md border border-foreground/10 px-5 py-2.5 text-sm text-muted hover:text-foreground"
          >
            {t("saveArtLater")}
          </button>
        </div>
      </div>
    </div>
  );
}
