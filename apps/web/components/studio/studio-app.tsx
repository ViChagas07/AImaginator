"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {
  Check,
  Download,
  ImagePlus,
  Loader2,
  Maximize2,
  Pencil,
  RefreshCw,
  Send,
  Sparkles,
  TriangleAlert,
  Upload,
  WandSparkles,
  X,
} from "lucide-react";
import {useAuthStore} from "@/stores/auth";
import {
  isGeneratingStatus,
  useGenerationStore,
  type GenerationErrorMessages,
} from "@/stores/generation";
import type {GenerationRecord} from "@/lib/generation-contract";
import {AIGeneratingLoader} from "@/components/ui/ai-generating-loader";
import {CancelGenerationModal} from "@/components/studio/cancel-generation-modal";
import {LoginGateModal} from "@/components/studio/login-gate-modal";
import {
  ASPECT_RATIOS,
  STYLE_PRESETS,
  isAspectRatio,
  UPLOAD_MAX_DIMENSION,
  UPLOAD_MAX_MB,
  UploadValidationError,
  validateUploadFile,
  type UploadErrorCode,
} from "@/lib/studio-config";
import {API_BASE_URL} from "@/lib/constants";
import {cn} from "@/lib/utils";

function uploadErrorMessage(
  code: UploadErrorCode | null,
  t: ReturnType<typeof useTranslations<"studio">>,
): string | null {
  if (!code) return null;
  if (code === "type") return t("uploadInvalidType");
  if (code === "size") return t("uploadTooLarge", {size: UPLOAD_MAX_MB});
  return t("uploadInvalidDimensions", {max: UPLOAD_MAX_DIMENSION});
}

function formatDate(value: string, locale: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(locale, {dateStyle: "medium", timeStyle: "short"});
}

function downloadHref(url: string, id: string): string {
  if (!/^https?:\/\//i.test(url)) return url;
  const filename = encodeURIComponent(`aimaginator-${id}.png`);
  return `/api/download?url=${encodeURIComponent(url)}&filename=${filename}`;
}

export function StudioApp({initialPrompt}: {initialPrompt?: string}) {
  const t = useTranslations("studio");
  const tErrors = useTranslations("errors");
  const tGallery = useTranslations("gallery");
  const locale = useLocale();
  const auth = useAuthStore();
  const gen = useGenerationStore();
  const fileRef = useRef<HTMLInputElement>(null);
  const refinePanelRef = useRef<HTMLElement>(null);
  const sessionGalleryRef = useRef<HTMLUListElement>(null);
  const [dismissedResultUrl, setDismissedResultUrl] = useState<string | null>(null);
  const [cancelTargetId, setCancelTargetId] = useState<string | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<UploadErrorCode | null>(null);
  const [refineTarget, setRefineTarget] = useState<GenerationRecord | null>(null);
  const [refineInstruction, setRefineInstruction] = useState("");
  const [seedInvalid, setSeedInvalid] = useState(false);
  const [featureEnabled, setFeatureEnabled] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  const isAuthenticated = auth.status === "authenticated";
  const isGenerating = isGeneratingStatus(gen.status);
  const isEditMode = gen.mode === "edit";
  const newestSessionId = gen.sessionResults[0]?.id ?? null;
  const indeterminateProgress =
    isGenerating && (gen.progress <= 0 || gen.streamDegraded);
  const stageLabel =
    gen.status === "processing" && gen.stage ? t(`stage.${gen.stage}`) : null;
  const cancelModalOpen =
    cancelTargetId !== null &&
    cancelTargetId === gen.result?.id &&
    isGenerating;
  const errorMessages: GenerationErrorMessages = useMemo(
    () => ({
      http: (status: number) => tErrors("generationHttp", {status}),
      failed: tErrors("generationFailed"),
      network: tErrors("generationNetwork"),
      alreadyFinished: tErrors("generationAlreadyFinished"),
      cancelTimeout: tErrors("generationCancelTimeout"),
    }),
    [tErrors],
  );

  useEffect(() => {
    void auth.fetchMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE_URL}/api/v1/config`, {cache: "no-store"})
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: unknown) => {
        if (!active || !payload || typeof payload !== "object") return;
        const enabled = (payload as {image_generation_enabled?: unknown})
          .image_generation_enabled;
        if (typeof enabled === "boolean") setFeatureEnabled(enabled);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (initialPrompt) gen.setPrompt(initialPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  useEffect(() => {
    if (auth.status === "authenticated") void gen.loadHistory(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  useEffect(() => {
    return () => {
      if (uploadPreview) URL.revokeObjectURL(uploadPreview);
    };
  }, [uploadPreview]);

  useEffect(() => {
    if (!newestSessionId) return;
    sessionGalleryRef.current?.scrollTo({left: 0, behavior: "smooth"});
  }, [newestSessionId]);

  const requireLoginToSave =
    process.env.NODE_ENV === "production" &&
    process.env.NEXT_PUBLIC_REQUIRE_LOGIN_TO_SAVE !== "false";

  const showLoginGate =
    requireLoginToSave &&
    gen.status === "done" &&
    auth.status === "unauthenticated" &&
    gen.resultUrl !== dismissedResultUrl;

  async function acceptFile(file: File | null) {
    if (!file) return;
    setUploadError(null);
    try {
      await validateUploadFile(file);
      if (uploadPreview) URL.revokeObjectURL(uploadPreview);
      setUploadPreview(URL.createObjectURL(file));
      gen.setUploadFile(file);
      gen.setMode("edit");
    } catch (error) {
      gen.setUploadFile(null);
      setUploadError(
        error instanceof UploadValidationError ? error.code : "type",
      );
    }
  }

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    void acceptFile(file);
    event.target.value = "";
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0] ?? null;
    void acceptFile(file);
  }

  function selectMode(mode: "generate" | "edit") {
    if (mode === "edit" && !isAuthenticated) return;
    gen.setMode(mode);
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (seedInvalid) return;
    const prompt = gen.prompt.trim();
    if (!prompt) return;
    if (isEditMode) {
      if (!isAuthenticated || !gen.uploadFile) return;
      void gen.startEditUpload(prompt, errorMessages, locale);
      return;
    }
    void gen.startGeneration(prompt, errorMessages, locale);
  }

  function openRefine(target: GenerationRecord) {
    if (!isAuthenticated) return;
    setRefineTarget(target);
    setRefineInstruction("");
    window.setTimeout(
      () => refinePanelRef.current?.scrollIntoView({behavior: "smooth", block: "start"}),
      0,
    );
  }

  function submitRefine(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!refineTarget || !refineInstruction.trim()) return;
    const ratio = isAspectRatio(refineTarget.aspectRatio)
      ? refineTarget.aspectRatio
      : "1:1";
    void gen.startRefine(
      refineTarget.id,
      refineInstruction.trim(),
      ratio,
      errorMessages,
      locale,
    );
    setRefineTarget(null);
    setRefineInstruction("");
  }

  function startRename(item: GenerationRecord) {
    setRenamingId(item.id);
    setRenameDraft(item.title ?? "");
  }

  async function commitRename(id: string) {
    const title = renameDraft.trim();
    if (!title) return;
    const renamed = await gen.renameGeneration(id, title);
    if (renamed) setRenamingId(null);
  }

  function handleSeedChange(value: string) {
    gen.setSeed(value);
    if (!value.trim()) {
      setSeedInvalid(false);
      return;
    }
    setSeedInvalid(!/^\d+$/.test(value) || Number(value) > 2 ** 32 - 1);
  }

  const clientUploadMessage = uploadErrorMessage(uploadError, t);

  if (auth.status === "unknown") {
    return (
      <div className="rounded-xl border border-foreground/10 bg-surface p-8">
        <p className="text-muted">{t("loadingAuth")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {!featureEnabled && (
        <p role="status" className="rounded-lg border border-foreground/10 bg-surface p-4 text-sm text-muted">
          {t("comingSoon")}
        </p>
      )}

      <div
        role="tablist"
        aria-label={t("modeTablistLabel")}
        className="inline-flex rounded-full border border-foreground/10 bg-surface p-1"
      >
        <button
          type="button"
          role="tab"
          aria-selected={!isEditMode}
          onClick={() => selectMode("generate")}
          className={cn(
            "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
            !isEditMode
              ? "bg-accent-gradient text-foreground"
              : "text-muted hover:text-foreground",
          )}
        >
          <Sparkles className="h-4 w-4" aria-hidden />
          {t("modeGenerate")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={isEditMode}
          aria-disabled={!isAuthenticated}
          onClick={() => selectMode("edit")}
          className={cn(
            "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
            isEditMode
              ? "bg-accent-gradient text-foreground"
              : "text-muted hover:text-foreground",
            !isAuthenticated && "cursor-not-allowed opacity-50",
          )}
        >
          <WandSparkles className="h-4 w-4" aria-hidden />
          {t("modeEdit")}
        </button>
      </div>

      {!isAuthenticated && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
          {t("editLoginRequired")}
          <a
            href={auth.loginUrl}
            className="inline-flex items-center gap-1 rounded-md border border-foreground/10 px-3 py-1.5 text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
          >
            {t("editLoginCta")}
          </a>
        </p>
      )}

      <form onSubmit={submit} data-testid="studio-form" className="space-y-5">
        <div>
          <label
            htmlFor="studio-prompt"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            {isEditMode ? t("editPromptLabel") : t("promptLabel")}
          </label>
          <textarea
            id="studio-prompt"
            value={gen.prompt}
            onChange={(event) => gen.setPrompt(event.target.value)}
            placeholder={
              isEditMode
                ? t("editPromptPlaceholder")
                : t("promptPlaceholder")
            }
            rows={3}
            className="w-full rounded-xl border border-foreground/10 bg-surface-raised p-4 text-base text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
          />
        </div>

        {isEditMode && (
          <div>
            <p className="mb-2 text-sm font-medium text-foreground">
              {t("editUploadLabel")}
            </p>
            {!uploadPreview ? (
              <div
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
                className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-foreground/20 bg-surface p-8 text-center"
              >
                <Upload className="h-8 w-8 text-muted" aria-hidden />
                <p className="text-sm text-muted">{t("uploadDrop")}</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={handleFile}
                  className="sr-only"
                  aria-label={t("uploadChoose")}
                />
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-md border border-foreground/10 bg-surface-raised px-4 py-2 text-sm text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                >
                  <ImagePlus className="h-4 w-4" aria-hidden />
                  {t("uploadChoose")}
                </button>
                <p className="text-xs text-muted">
                  {t("uploadMaxHint", {
                    size: UPLOAD_MAX_MB,
                    max: UPLOAD_MAX_DIMENSION,
                  })}
                </p>
              </div>
            ) : (
              <div className="relative inline-block">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={uploadPreview}
                  alt={t("uploadPreviewAlt")}
                  className="max-h-56 rounded-lg border border-foreground/10"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (uploadPreview) URL.revokeObjectURL(uploadPreview);
                    setUploadPreview(null);
                    gen.setUploadFile(null);
                    setUploadError(null);
                  }}
                  aria-label={t("uploadRemove")}
                  title={t("uploadRemove")}
                  className="absolute end-2 top-2 flex h-8 w-8 items-center justify-center rounded-full border border-foreground/10 bg-surface text-muted hover:text-foreground focus-visible:border-accent-to"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="mt-2 inline-flex items-center gap-2 text-sm text-muted hover:text-foreground"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden />
                  {t("uploadReplace")}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={handleFile}
                  className="sr-only"
                  aria-label={t("uploadReplace")}
                />
              </div>
            )}
            {!gen.uploadFile && !clientUploadMessage && (
              <p className="mt-2 text-xs text-muted">{t("uploadRequired")}</p>
            )}
            {clientUploadMessage && (
              <p role="alert" className="mt-2 flex items-center gap-2 text-sm text-foreground">
                <TriangleAlert className="h-4 w-4" aria-hidden />
                {`${t("uploadErrorLabel")}: ${clientUploadMessage}`}
              </p>
            )}
          </div>
        )}

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-foreground">
            {t("aspectRatioLabel")}
          </legend>
          <div
            role="radiogroup"
            aria-label={t("aspectRatioGroupLabel")}
            className="flex flex-wrap gap-2"
          >
            {ASPECT_RATIOS.map((ratio) => {
              const selected = gen.aspectRatio === ratio.value;
              return (
                <button
                  key={ratio.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => gen.setAspectRatio(ratio.value)}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-start text-sm transition-colors focus-visible:border-accent-to",
                    selected
                      ? "border-accent-to bg-white/[0.08] text-foreground"
                      : "border-foreground/10 bg-surface text-muted hover:text-foreground",
                  )}
                >
                  <span className="block font-semibold">{ratio.value}</span>
                  <span className="block text-xs">{t(ratio.labelKey)}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted">
            {t("aspectRatioPreview", {ratio: gen.aspectRatio})}
          </p>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-foreground">
            {t("styleLabel")}
          </legend>
          <div className="flex flex-wrap gap-2">
            {STYLE_PRESETS.map((preset) => {
              const selected = gen.stylePreset === preset.value;
              return (
                <button
                  key={preset.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => gen.setStylePreset(preset.value)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-sm transition-colors",
                    selected
                      ? "border-accent-to bg-white/[0.08] text-foreground"
                      : "border-foreground/10 bg-surface text-muted hover:text-foreground",
                  )}
                >
                  {t(preset.labelKey)}
                </button>
              );
            })}
          </div>
        </fieldset>

        <details className="rounded-lg border border-foreground/10 bg-surface p-4">
          <summary className="cursor-pointer text-sm font-medium text-foreground">
            {t("seedAdvanced")}
          </summary>
          <div className="mt-3 max-w-xs space-y-2">
            <label htmlFor="studio-seed" className="block text-sm text-foreground">
              {t("seedLabel")}
            </label>
            <input
              id="studio-seed"
              type="number"
              inputMode="numeric"
              min={0}
              max={2 ** 32 - 1}
              value={gen.seed}
              onChange={(event) => handleSeedChange(event.target.value)}
              placeholder={t("seedPlaceholder")}
              aria-invalid={seedInvalid}
              className="w-full rounded-md border border-foreground/10 bg-surface-raised px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
            />
            <p className="text-xs text-muted">{t("seedHint")}</p>
            {seedInvalid && (
              <p role="alert" className="text-xs text-foreground">
                {t("seedInvalid")}
              </p>
            )}
          </div>
        </details>

        <button
          type="submit"
          disabled={
            isGenerating ||
            !featureEnabled ||
            !gen.prompt.trim() ||
            seedInvalid ||
            (isEditMode && (!isAuthenticated || !gen.uploadFile))
          }
          aria-busy={isGenerating}
          className="bg-accent-gradient inline-flex items-center gap-2 rounded-md px-6 py-3 text-base font-semibold text-foreground disabled:opacity-50"
        >
          {isGenerating ? (
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          ) : (
            <Send className="h-5 w-5" aria-hidden />
          )}
          {isGenerating
            ? t("generatingButton")
            : isEditMode
              ? t("editSubmit")
              : t("generateButton")}
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
          {stageLabel ? ` · ${stageLabel}` : ""}
        </p>
        {isGenerating && (
          <p className="text-xs text-muted">
            {isEditMode ? t("timeEstimateEdit") : t("timeEstimateGenerate")}
          </p>
        )}
        {(isGenerating || gen.status === "done") && (
          <div
            role="progressbar"
            aria-valuenow={indeterminateProgress ? undefined : gen.progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuetext={stageLabel ?? undefined}
            aria-label={t("progressLabel")}
            className="h-2 w-full overflow-hidden rounded-full bg-surface"
          >
            <div
              className={cn(
                "bg-accent-gradient h-full rounded-full transition-[width] duration-300",
                indeterminateProgress && "w-full animate-pulse",
              )}
              style={
                indeterminateProgress
                  ? undefined
                  : {width: `${gen.progress}%`}
              }
            />
          </div>
        )}
        {isGenerating && gen.result ? (
          <button
            type="button"
            onClick={() => setCancelTargetId(gen.result?.id ?? null)}
            disabled={gen.canceling}
            className="rounded-md border border-foreground/10 px-3 py-1.5 text-xs text-muted hover:text-foreground disabled:opacity-50"
          >
            {gen.canceling ? t("canceling") : t("cancel")}
          </button>
        ) : null}
        {gen.status === "failed" && gen.error && (
          <p role="alert" className="flex items-center gap-2 text-sm text-foreground">
            <TriangleAlert className="h-4 w-4" aria-hidden />
            {`${t("errorLabel")}: ${gen.error}`}
          </p>
        )}
        {gen.warning && (
          <p role="status" className="text-sm text-muted">
            {gen.warning}
          </p>
        )}
        {gen.sessionResults.length > 0 && (
          <div className="space-y-3">
            <ul
              ref={sessionGalleryRef}
              data-testid="session-gallery"
              aria-label={t("resultLabel")}
              dir="ltr"
              className="flex gap-4 overflow-x-auto pb-2"
            >
              {gen.sessionResults.map((item) => {
                const parent = item.parentGenerationId
                  ? gen.history.find(
                      (candidate) => candidate.id === item.parentGenerationId,
                    ) ??
                    gen.sessionResults.find(
                      (candidate) => candidate.id === item.parentGenerationId,
                    )
                  : null;
                return (
                  <li
                    key={item.id}
                    className="w-72 max-w-[85vw] shrink-0 overflow-hidden rounded-xl border border-foreground/10 bg-surface"
                  >
                    {item.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.imageUrl}
                        alt={item.title ?? (item.prompt || t("resultAlt"))}
                        className="aspect-square w-full object-cover"
                      />
                    ) : null}
                    <div className="space-y-2 p-3 text-start">
                      {renamingId === item.id ? (
                        <form
                          onSubmit={(event) => {
                            event.preventDefault();
                            void commitRename(item.id);
                          }}
                          className="flex items-center gap-1"
                        >
                          <input
                            value={renameDraft}
                            onChange={(event) => setRenameDraft(event.target.value)}
                            placeholder={item.prompt}
                            aria-label={tGallery("renameLabel")}
                            className="min-w-0 flex-1 rounded border border-foreground/10 bg-surface-raised px-2 py-1 text-xs text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
                          />
                          <button
                            type="submit"
                            aria-label={tGallery("saveRename")}
                            title={tGallery("saveRename")}
                            className="text-muted hover:text-foreground"
                          >
                            <Check className="h-4 w-4" aria-hidden />
                          </button>
                          <button
                            type="button"
                            onClick={() => setRenamingId(null)}
                            aria-label={tGallery("cancelRename")}
                            title={tGallery("cancelRename")}
                            className="text-muted hover:text-foreground"
                          >
                            <X className="h-4 w-4" aria-hidden />
                          </button>
                        </form>
                      ) : (
                        <div className="flex items-start justify-between gap-2">
                          <p className="line-clamp-2 text-sm text-foreground">
                            {item.title ?? item.prompt}
                          </p>
                          <button
                            type="button"
                            onClick={() => startRename(item)}
                            aria-label={tGallery("rename")}
                            title={tGallery("rename")}
                            className="shrink-0 text-muted hover:text-foreground focus-visible:border-accent-to"
                          >
                            <Pencil className="h-3.5 w-3.5" aria-hidden />
                          </button>
                        </div>
                      )}
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                        {item.seed !== null && (
                          <span>{t("seedValue", {seed: item.seed})}</span>
                        )}
                        <span>{t("aspectRatioPreview", {ratio: item.aspectRatio})}</span>
                      </div>
                      {item.parentGenerationId && (
                        <p className="line-clamp-1 text-xs text-muted">
                          {t("historyChain", {
                            prompt: parent?.prompt ?? t("historyChainUnknown"),
                          })}
                        </p>
                      )}
                      <div
                        aria-label={t("resultActionsLabel")}
                        className="flex flex-wrap gap-1.5"
                      >
                        {item.imageUrl && (
                          <a
                            href={downloadHref(item.imageUrl, item.id)}
                            download
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 rounded-md border border-foreground/10 bg-surface px-2 py-1.5 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                          >
                            <Download className="h-3.5 w-3.5" aria-hidden />
                            {t("download")}
                          </a>
                        )}
                        {isAuthenticated && item.kind === "generate" && (
                          <button
                            type="button"
                            disabled={isGenerating}
                            onClick={() =>
                              void gen.startVariation(item.id, errorMessages, locale)
                            }
                            className="inline-flex items-center gap-1.5 rounded-md border border-foreground/10 bg-surface px-2 py-1.5 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to disabled:opacity-50"
                          >
                            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                            {t("generateVariation")}
                          </button>
                        )}
                        {isAuthenticated && (
                          <button
                            type="button"
                            disabled={isGenerating}
                            onClick={() => openRefine(item)}
                            className="inline-flex items-center gap-1.5 rounded-md border border-foreground/10 bg-surface px-2 py-1.5 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to disabled:opacity-50"
                          >
                            <WandSparkles className="h-3.5 w-3.5" aria-hidden />
                            {t("refine")}
                          </button>
                        )}
                        {isAuthenticated && (
                          <button
                            type="button"
                            disabled={isGenerating}
                            onClick={() =>
                              void gen.startUpscale(item.id, errorMessages, locale)
                            }
                            className="inline-flex items-center gap-1.5 rounded-md border border-foreground/10 bg-surface px-2 py-1.5 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to disabled:opacity-50"
                          >
                            <Maximize2 className="h-3.5 w-3.5" aria-hidden />
                            {isGenerating &&
                            gen.result?.id === item.id &&
                            item.kind === "upscale"
                              ? t("upscaling")
                              : t("upscale")}
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            {gen.upscaleRemaining !== null && (
              <p className="text-xs text-muted">
                {t("upscaleRemaining", {count: gen.upscaleRemaining})}
              </p>
            )}
          </div>
        )}
      </section>

      {refineTarget && (
        <section
          ref={refinePanelRef}
          aria-labelledby="refine-heading"
          className="rounded-xl border border-foreground/10 bg-surface p-4"
        >
          <h2 id="refine-heading" className="mb-2 text-lg font-semibold text-foreground">
            {t("refineTitle")}
          </h2>
          <p className="mb-3 line-clamp-2 text-sm text-muted">{refineTarget.prompt}</p>
          <form onSubmit={submitRefine} className="space-y-3">
            <label htmlFor="refine-prompt" className="block text-sm text-foreground">
              {t("refinePromptLabel")}
            </label>
            <input
              id="refine-prompt"
              value={refineInstruction}
              onChange={(event) => setRefineInstruction(event.target.value)}
              placeholder={t("refinePromptPlaceholder")}
              className="w-full rounded-md border border-foreground/10 bg-surface-raised px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={!refineInstruction.trim() || isGenerating}
                className="bg-accent-gradient inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-foreground disabled:opacity-50"
              >
                <WandSparkles className="h-4 w-4" aria-hidden />
                {t("refineSubmit")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setRefineTarget(null);
                  setRefineInstruction("");
                }}
                className="inline-flex items-center gap-2 rounded-md border border-foreground/10 px-4 py-2 text-sm text-muted hover:text-foreground focus-visible:border-accent-to"
              >
                {t("refineCancel")}
              </button>
            </div>
          </form>
        </section>
      )}

      <section aria-labelledby="history-heading">
        <h2
          id="history-heading"
          className="mb-4 text-xl font-semibold tracking-tight text-foreground"
        >
          {t("historyTitle")}
        </h2>
        {!isAuthenticated ? (
          <p className="text-sm text-muted">{t("anonymousHistory")}</p>
        ) : gen.history.length === 0 ? (
          <p className="text-sm text-muted">{t("historyEmpty")}</p>
        ) : (
          <>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {gen.history.map((item) => {
                const parent = item.parentGenerationId
                  ? gen.history.find((candidate) => candidate.id === item.parentGenerationId)
                  : null;
                return (
                  <li
                    key={item.id}
                    className="overflow-hidden rounded-lg border border-foreground/10 bg-surface"
                  >
                    {item.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.imageUrl}
                        alt={item.prompt}
                        loading="lazy"
                        className="aspect-square w-full object-cover"
                      />
                    ) : (
                      <div className="flex aspect-square items-center justify-center bg-surface-raised text-xs text-muted">
                        {t(`status.${item.status}`)}
                      </div>
                    )}
                    <div className="space-y-2 p-3 text-start">
                      <p className="line-clamp-2 text-sm text-foreground">{item.prompt}</p>
                      <p className="text-xs text-muted">
                        {formatDate(item.createdAt, locale)}
                      </p>
                      <p className="text-xs text-muted">
                        {item.aspectRatio}
                        {item.seed !== null ? ` · ${t("seedValue", {seed: item.seed})}` : ""}
                      </p>
                      {parent && (
                        <p className="line-clamp-1 text-xs text-muted">
                          {t("historyChain", {prompt: parent.prompt})}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          onClick={() => gen.showResult(item)}
                          className="rounded border border-foreground/10 px-2 py-1 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                        >
                          {t("historyOpen")}
                        </button>
                        {item.kind === "generate" && item.status === "done" && (
                          <button
                            type="button"
                            onClick={() =>
                              void gen.startVariation(item.id, errorMessages, locale)
                            }
                            className="rounded border border-foreground/10 px-2 py-1 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                          >
                            {t("historyVariation")}
                          </button>
                        )}
                        {item.status === "done" && (
                          <button
                            type="button"
                            onClick={() => openRefine(item)}
                            className="rounded border border-foreground/10 px-2 py-1 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                          >
                            {t("historyRefine")}
                          </button>
                        )}
                        {isAuthenticated && item.status === "done" && (
                          <button
                            type="button"
                            onClick={() =>
                              void gen.startUpscale(item.id, errorMessages, locale)
                            }
                            className="rounded border border-foreground/10 px-2 py-1 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                          >
                            {t("upscale")}
                          </button>
                        )}
                        {item.imageUrl && (
                          <a
                            href={downloadHref(item.imageUrl, item.id)}
                            download
                            target="_blank"
                            rel="noreferrer"
                            className="rounded border border-foreground/10 px-2 py-1 text-xs text-foreground hover:bg-white/[0.06] focus-visible:border-accent-to"
                          >
                            {t("historyDownload")}
                          </a>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            {gen.historyCursor && (
              <div className="mt-6 flex justify-center">
                <button
                  type="button"
                  onClick={() => void gen.loadHistory(false)}
                  disabled={gen.historyLoading}
                  className="inline-flex items-center gap-2 rounded-md bg-surface-raised px-4 py-2 text-sm text-foreground disabled:opacity-50"
                >
                  {gen.historyLoading && (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  )}
                  {t("historyLoadMore")}
                </button>
              </div>
            )}
          </>
        )}
      </section>

      <LoginGateModal
        open={showLoginGate}
        onDismiss={() => setDismissedResultUrl(gen.resultUrl)}
      />
      <CancelGenerationModal
        open={cancelModalOpen}
        canceling={gen.canceling}
        error={gen.error}
        onConfirm={async () => {
          const requested = await gen.cancelGeneration(errorMessages);
          if (requested) setCancelTargetId(null);
        }}
        onClose={() => setCancelTargetId(null)}
      />
    </div>
  );
}
