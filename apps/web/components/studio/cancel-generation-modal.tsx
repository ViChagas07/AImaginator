"use client";

import {useTranslations} from "next-intl";
import {Loader2} from "lucide-react";

export function CancelGenerationModal({
  open,
  canceling,
  error,
  onConfirm,
  onClose,
}: {
  open: boolean;
  canceling: boolean;
  error: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useTranslations("studio");
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-generation-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        aria-label={t("cancelKeep")}
        onClick={onClose}
        disabled={canceling}
        className="absolute inset-0 cursor-default bg-black/50 disabled:cursor-not-allowed"
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border border-foreground/10 bg-surface p-6 shadow-2xl">
        <h2
          id="cancel-generation-title"
          className="text-xl font-semibold text-foreground"
        >
          {t("cancelTitle")}
        </h2>
        <p className="mt-2 text-sm text-muted">{t("cancelBody")}</p>
        {error && (
          <p role="alert" className="mt-3 text-sm text-foreground">
            {error}
          </p>
        )}
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onConfirm}
            disabled={canceling}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-red-500 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {canceling && (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            )}
            {canceling ? t("canceling") : t("cancel")}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={canceling}
            className="inline-flex items-center justify-center rounded-md border border-foreground/10 px-5 py-2.5 text-sm text-muted hover:text-foreground disabled:opacity-50"
          >
            {t("cancelKeep")}
          </button>
        </div>
      </div>
    </div>
  );
}
