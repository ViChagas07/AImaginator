"use client";

import {useEffect, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import Link from "next/link";
import {Loader2, Send, TriangleAlert, X, Lock} from "lucide-react";
import {useAuthStore} from "@/stores/auth";
import {isGeneratingStatus, useGenerationStore} from "@/stores/generation";
import {AIGeneratingLoader} from "@/components/ui/ai-generating-loader";
import {LoginGateModal} from "@/components/studio/login-gate-modal";

export function StudioApp({initialPrompt}: {initialPrompt?: string}) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const locale = useLocale();
  const auth = useAuthStore();
  const gen = useGenerationStore();
  const fileRef = useRef<HTMLInputElement>(null);
  const imageBase64 = gen.imageBase64;
  const [dismissedResultUrl, setDismissedResultUrl] = useState<string | null>(null);

  useEffect(() => {
    void auth.fetchMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (initialPrompt) gen.setPrompt(initialPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  useEffect(() => {
    if (auth.status === "authenticated") void gen.loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  // Login-gate pós-geração para anônimos (Bloco 3-A): a arte já está
  // associada à sessão anônima e será migrada ao efetuar login/cadastro.
  const showLoginGate =
    gen.status === "done" &&
    auth.status === "unauthenticated" &&
    gen.resultUrl !== dismissedResultUrl;

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => gen.setImage(reader.result as string);
    reader.readAsDataURL(file);
    event.target.value = "";
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!gen.prompt.trim()) return;
    void gen.startGeneration(gen.prompt.trim(), imageBase64, {
      http: (status) => tErrors("generationHttp", {status}),
      failed: tErrors("generationFailed"),
      network: tErrors("generationNetwork"),
    });
  }

  if (auth.status === "unknown") {
    return (
      <div className="rounded-xl border border-foreground/10 bg-surface p-8">
        <p className="text-muted">{t("loadingAuth")}</p>
      </div>
    );
  }

  const isGenerating = isGeneratingStatus(gen.status);

  // Avisos baseados no estado de autenticação
  const comingSoon = t("comingSoon");
  const loginToPrompt = t("loginToPrompt");

  const isAuthenticated = auth.status === "authenticated";
  const isUnauthenticated = auth.status === "unauthenticated";

  return (
    <div className="space-y-10">
      <form onSubmit={handleSubmit} className="space-y-4 relative">
        {/* Overlay para usuário NÃO autenticado: "✨ Entre Para Imaginar! ✨" */}
        {isUnauthenticated && (
          <Link
            href={`/${locale}/login`}
            className="absolute inset-0 rounded-xl bg-background/60 backdrop-blur flex items-center justify-center"
            aria-label={loginToPrompt}
          >
            <div className="text-center px-3" role="button" tabIndex={0}>
              <Lock className="h-4 w-4 text-primary mx-auto mb-1" aria-hidden />
              <p className="text-xs text-primary font-medium">{loginToPrompt}</p>
            </div>
          </Link>
        )}

        {/* Overlay para usuário autenticado: "em breve" (IA ainda não implementada) */}
        {isAuthenticated && (
          <div className="absolute inset-0 rounded-xl bg-background/60 backdrop-blur flex items-center justify-center pointer-events-none">
            <div className="text-center px-3" role="alert" aria-live="polite">
              <TriangleAlert className="h-4 w-4 text-destructive mx-auto mb-1" aria-hidden />
              <p className="text-xs text-destructive font-medium">{comingSoon}</p>
            </div>
          </div>
        )}

        <div>
          <label
            htmlFor="studio-prompt"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            {t("promptLabel")}
          </label>
          <textarea
            id="studio-prompt"
            value={gen.prompt}
            onChange={(e) => gen.setPrompt(e.target.value)}
            placeholder={t("promptPlaceholder")}
            rows={3}
            className="w-full rounded-xl border border-foreground/10 bg-surface-raised p-4 text-base text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
          />
        </div>
        <div>
          <label
            htmlFor="studio-upload"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            {t("uploadLabel")}
          </label>
          <input
            ref={fileRef}
            id="studio-upload"
            type="file"
            accept="image/png,image/jpeg"
            onChange={handleFile}
            className="block w-full text-sm text-muted file:mr-4 file:rounded-md file:border file:border-foreground/10 file:bg-surface file:px-4 file:py-2 file:text-foreground"
            aria-describedby="upload-hint"
          />
          <p id="upload-hint" className="mt-1 text-xs text-muted">
            {t("uploadHint")}
          </p>
          {imageBase64 && (
            <div className="relative mt-3 inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageBase64}
                alt={tCommon("attachedImageAlt")}
                className="max-h-40 rounded-lg border border-foreground/10"
              />
              <button
                type="button"
                onClick={() => gen.setImage(undefined)}
                aria-label={tCommon("removeImage")}
                title={tCommon("removeImage")}
                className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full border border-foreground/10 bg-surface text-muted hover:text-foreground focus-visible:outline-none"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          )}
        </div>
        <button
          type="submit"
          disabled={isGenerating || !gen.prompt.trim()}
          aria-busy={isGenerating}
          className="bg-accent-gradient inline-flex items-center gap-2 rounded-md px-6 py-3 text-base font-semibold text-foreground disabled:opacity-50"
        >
          {isGenerating ? (
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          ) : (
            <Send className="h-5 w-5" aria-hidden />
          )}
          {isGenerating ? t("generatingButton") : t("generateButton")}
        </button>
      </form>

      <section aria-label={t("progressLabel")} className="space-y-3">
        {isGenerating && (
          <div className="flex justify-center py-2">
            <AIGeneratingLoader />
          </div>
        )}
        <p className="text-sm text-muted" role="status" aria-live="polite">
          {t(`status.${gen.status}`)}
        </p>
        {(isGenerating || gen.status === "done") && (
          <div
            role="progressbar"
            aria-valuenow={gen.progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("progressLabel")}
            className="h-2 w-full overflow-hidden rounded-full bg-surface"
          >
            <div
              className="bg-accent-gradient h-full rounded-full transition-[width] duration-300"
              style={{width: `${gen.progress}%`}}
            />
          </div>
        )}
        {gen.status === "failed" && gen.error && (
          <p role="alert" className="flex items-center gap-2 text-sm text-foreground">
            <TriangleAlert className="h-4 w-4" aria-hidden />
            {`${t("errorLabel")}: ${gen.error}`}
          </p>
        )}
        {gen.resultUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={gen.resultUrl}
            alt={t("resultAlt")}
            className="max-h-[480px] rounded-xl border border-foreground/10"
          />
        )}
      </section>

      <section aria-labelledby="history-heading">
        <h2
          id="history-heading"
          className="mb-4 text-xl font-semibold tracking-tight text-foreground"
        >
          {t("historyTitle")}
        </h2>
        {gen.history.length === 0 ? (
          <p className="text-sm text-muted">{t("historyEmpty")}</p>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-3">
            {gen.history.map((item) => (
              <li
                key={item.id}
                className="rounded-lg border border-foreground/10 bg-surface p-3"
              >
                <p className="line-clamp-2 text-sm text-muted">{item.prompt}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <LoginGateModal
        open={showLoginGate}
        onDismiss={() => setDismissedResultUrl(gen.resultUrl)}
      />
    </div>
  );
}
