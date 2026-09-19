"use client";

import * as React from "react";
import {useEffect, useState, useCallback} from "react";
import {
  Settings as SettingsIcon,
  Palette,
  Globe,
  Accessibility,
  Bell,
  Shield,
  Wrench,
  Check,
  Loader2,
  AlertTriangle,
  FileDown,
  Trash2,
  RotateCcw,
  Eraser,
  Download,
} from "lucide-react";
import {useTranslations} from "next-intl";
import {Link} from "@/i18n/navigation";
import {routing} from "@/i18n/routing";
import {useSettingsStore, type UserSettings} from "@/stores/settings";
import {useToast} from "@/components/ui/toast";
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

const LANGUAGE_FLAGS: Record<AppLocale, string> = {
  "pt-BR": "🇧🇷",
  en: "🇺🇸",
  es: "🇪🇸",
  fr: "🇫🇷",
  de: "🇩🇪",
  ja: "🇯🇵",
  zh: "🇨🇳",
  ru: "🇷🇺",
  ar: "🇸🇦",
};

type TabId =
  | "appearance"
  | "languageRegion"
  | "accessibility"
  | "notifications"
  | "privacyData"
  | "advanced";

const TABS: {id: TabId; icon: React.ComponentType<{className?: string; "aria-hidden"?: boolean}>}[] = [
  {id: "appearance", icon: Palette},
  {id: "languageRegion", icon: Globe},
  {id: "accessibility", icon: Accessibility},
  {id: "notifications", icon: Bell},
  {id: "privacyData", icon: Shield},
  {id: "advanced", icon: Wrench},
];

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
}) {
  const id = React.useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {label}
        </label>
        {description && <p className="mt-1 text-xs text-muted">{description}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:border-accent-to focus-visible:outline-none",
          checked ? "bg-accent-gradient" : "bg-surface-raised border border-foreground/10",
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
            checked ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}

function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: {value: T; label: string}[];
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="ml-4 inline-flex rounded-lg border border-foreground/10 bg-surface p-1">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:border-accent-to focus-visible:outline-none",
              active
                ? "bg-accent-gradient text-foreground"
                : "text-muted hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ConfirmationModal({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  destructive,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onCancel} aria-hidden />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-md rounded-xl border border-foreground/10 bg-surface p-6 shadow-2xl"
      >
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-sm text-muted">{description}</p>
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-foreground/10 px-4 py-2 text-sm font-medium text-muted hover:text-foreground transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors",
              destructive ? "bg-red-600 hover:bg-red-500" : "bg-accent-gradient",
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const t = useTranslations("settings");
  const {toast} = useToast();
  const settings = useSettingsStore((s) => s.settings);
  const draft = useSettingsStore((s) => s.draft);
  const loading = useSettingsStore((s) => s.loading);
  const saving = useSettingsStore((s) => s.saving);
  const dirty = useSettingsStore((s) => s.dirty);
  const fetchSettings = useSettingsStore((s) => s.fetchSettings);
  const patchDraft = useSettingsStore((s) => s.patchDraft);
  const saveDraft = useSettingsStore((s) => s.saveDraft);
  const resetDraft = useSettingsStore((s) => s.resetDraft);

  const [activeTab, setActiveTab] = useState<TabId>("appearance");
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showResetAllConfirm, setShowResetAllConfirm] = useState(false);

  useEffect(() => {
    if (!settings) void fetchSettings();
  }, [settings, fetchSettings]);

  const patch = useCallback((partial: Partial<UserSettings>) => patchDraft(partial), [patchDraft]);

  const handleSave = useCallback(async () => {
    try {
      await saveDraft();
      toast.success(t("saved"));
    } catch {
      toast.error(t("saving"));
    }
  }, [saveDraft, toast, t]);

  const handleReset = useCallback(async () => {
    try {
      await resetDraft();
      setShowResetConfirm(false);
      setShowResetAllConfirm(false);
      toast.success(t("saved"));
    } catch {
      toast.error(t("saving"));
    }
  }, [resetDraft, toast, t]);

  if (loading && !settings) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center sm:px-6">
        <p className="text-muted">…</p>
      </div>
    );
  }

  if (!draft) return null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-gradient/20">
          <SettingsIcon className="h-6 w-6 text-accent-to" aria-hidden />
        </div>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
          <p className="mt-1 text-muted">{t("subtitle")}</p>
        </div>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Sidebar / mobile dropdown */}
        <nav
          aria-label={t("title")}
          className="lg:w-64 lg:shrink-0"
        >
          <ul className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
            {TABS.map((tab) => {
              const active = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <li key={tab.id} className="shrink-0 lg:shrink">
                  <button
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex w-full items-center gap-3 whitespace-nowrap rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:border-accent-to focus-visible:outline-none",
                      active
                        ? "bg-surface-raised text-foreground border border-foreground/10"
                        : "text-muted hover:text-foreground hover:bg-white/[0.04]",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    {t(`tabs.${tab.id}`)}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Panel */}
        <div className="flex-1">
          <div className="rounded-xl border border-foreground/10 bg-surface p-6">
            {activeTab === "appearance" && (
              <AppearanceTab draft={draft} patch={patch} />
            )}
            {activeTab === "languageRegion" && (
              <LanguageRegionTab draft={draft} patch={patch} />
            )}
            {activeTab === "accessibility" && (
              <AccessibilityTab draft={draft} patch={patch} />
            )}
            {activeTab === "notifications" && (
              <NotificationsTab draft={draft} patch={patch} />
            )}
            {activeTab === "privacyData" && (
              <PrivacyDataTab
                draft={draft}
                onExport={() => toast.success(t("privacyData.exportData.success"))}
                onDelete={() => setShowDeleteConfirm(true)}
              />
            )}
            {activeTab === "advanced" && (
              <AdvancedTab
                draft={draft}
                patch={patch}
                onExport={() => toast.success(t("privacyData.exportData.success"))}
                onResetAll={() => setShowResetAllConfirm(true)}
              />
            )}
          </div>

          {/* Fixed footer */}
          <div className="sticky bottom-0 mt-6 flex items-center justify-between gap-3 rounded-xl border border-foreground/10 bg-canvas/95 p-4 backdrop-blur">
            <button
              type="button"
              onClick={() => setShowResetConfirm(true)}
              className="rounded-md border border-foreground/10 px-4 py-2 text-sm font-medium text-muted hover:text-foreground transition-colors"
            >
              <RotateCcw className="mr-1 inline h-4 w-4" aria-hidden />
              {t("reset")}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!dirty || saving}
              className="bg-accent-gradient inline-flex items-center gap-2 rounded-md px-5 py-2 text-sm font-semibold text-foreground disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  {t("saving")}
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" aria-hidden />
                  {t("save")}
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <ConfirmationModal
        open={showResetConfirm}
        title={t("reset")}
        description={t("resetConfirm")}
        confirmLabel={t("reset")}
        cancelLabel={t("privacyData.deleteAccount.cancel")}
        onConfirm={handleReset}
        onCancel={() => setShowResetConfirm(false)}
      />
      <ConfirmationModal
        open={showDeleteConfirm}
        title={t("privacyData.deleteAccount.confirmTitle")}
        description={t("privacyData.deleteAccount.confirmDescription")}
        confirmLabel={t("privacyData.deleteAccount.confirm")}
        cancelLabel={t("privacyData.deleteAccount.cancel")}
        destructive
        onConfirm={() => {
          setShowDeleteConfirm(false);
          toast.warning(t("privacyData.deleteAccount.title"));
        }}
        onCancel={() => setShowDeleteConfirm(false)}
      />
      <ConfirmationModal
        open={showResetAllConfirm}
        title={t("advanced.resetAllSettings.confirmTitle")}
        description={t("advanced.resetAllSettings.confirmDescription")}
        confirmLabel={t("advanced.resetAllSettings.confirm")}
        cancelLabel={t("advanced.resetAllSettings.cancel")}
        destructive
        onConfirm={handleReset}
        onCancel={() => setShowResetAllConfirm(false)}
      />
    </div>
  );
}

function AppearanceTab({
  draft,
  patch,
}: {
  draft: UserSettings;
  patch: (partial: Partial<UserSettings>) => void;
}) {
  const t = useTranslations("settings");
  return (
    <section aria-labelledby="appearance-heading" className="space-y-8">
      <div>
        <h2 id="appearance-heading" className="text-lg font-semibold text-foreground">{t("appearance.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("appearance.description")}</p>
      </div>
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">{t("appearance.theme.label")}</span>
        <SegmentedControl
          label={t("appearance.theme.label")}
          value={draft.theme}
          onChange={(theme) => patch({theme})}
          options={[
            {value: "dark", label: t("appearance.theme.dark")},
            {value: "light", label: t("appearance.theme.light")},
            {value: "system", label: t("appearance.theme.system")},
          ]}
        />
      </div>
      <Toggle
        checked={draft.bold_text}
        onChange={(bold_text) => patch({bold_text})}
        label={t("appearance.boldText.label")}
        description={t("appearance.boldText.description")}
      />
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">{t("appearance.fontSize.label")}</span>
        <SegmentedControl
          label={t("appearance.fontSize.label")}
          value={draft.font_size}
          onChange={(font_size) => patch({font_size})}
          options={[
            {value: "small", label: t("appearance.fontSize.small")},
            {value: "medium", label: t("appearance.fontSize.medium")},
            {value: "large", label: t("appearance.fontSize.large")},
            {value: "xl", label: t("appearance.fontSize.xl")},
          ]}
        />
      </div>
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">{t("appearance.elementSpacing.label")}</span>
        <SegmentedControl
          label={t("appearance.elementSpacing.label")}
          value={draft.element_spacing}
          onChange={(element_spacing) => patch({element_spacing})}
          options={[
            {value: "compact", label: t("appearance.elementSpacing.compact")},
            {value: "comfortable", label: t("appearance.elementSpacing.comfortable")},
            {value: "spacious", label: t("appearance.elementSpacing.spacious")},
          ]}
        />
      </div>
    </section>
  );
}

function LanguageRegionTab({
  draft,
  patch,
}: {
  draft: UserSettings;
  patch: (partial: Partial<UserSettings>) => void;
}) {
  const t = useTranslations("settings");
  return (
    <section aria-labelledby="language-heading" className="space-y-8">
      <div>
        <h2 id="language-heading" className="text-lg font-semibold text-foreground">{t("languageRegion.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("languageRegion.description")}</p>
      </div>
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">{t("languageRegion.language.label")}</span>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {routing.locales.map((locale) => {
            const active = draft.locale === locale;
            return (
              <button
                key={locale}
                type="button"
                onClick={() => patch({locale})}
                aria-pressed={active}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors focus-visible:border-accent-to focus-visible:outline-none",
                  active
                    ? "border-accent-to bg-accent-gradient/10 text-foreground"
                    : "border-foreground/10 text-muted hover:text-foreground",
                )}
              >
                <span aria-hidden>{LANGUAGE_FLAGS[locale]}</span>
                <span className="truncate">{LANGUAGE_NAMES[locale]}</span>
                {active && <Check className="ml-auto h-4 w-4 shrink-0" aria-hidden />}
              </button>
            );
          })}
        </div>
      </div>
      <div className="space-y-2">
        <label htmlFor="timezone-select" className="text-sm font-medium text-foreground">
          {t("languageRegion.timezone.label")}
        </label>
        <select
          id="timezone-select"
          value={draft.timezone}
          onChange={(e) => patch({timezone: e.target.value})}
          className="w-full rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-foreground focus-visible:border-accent-to focus-visible:outline-none"
        >
          <option value="America/Sao_Paulo">Brasília (UTC-3)</option>
          <option value="America/New_York">New York (UTC-5)</option>
          <option value="America/Los_Angeles">Los Angeles (UTC-8)</option>
          <option value="Europe/London">London (UTC+0)</option>
          <option value="Europe/Paris">Paris (UTC+1)</option>
          <option value="Europe/Berlin">Berlin (UTC+1)</option>
          <option value="Asia/Tokyo">Tokyo (UTC+9)</option>
          <option value="Asia/Shanghai">Shanghai (UTC+8)</option>
          <option value="Australia/Sydney">Sydney (UTC+10)</option>
          <option value="UTC">UTC</option>
        </select>
        <p className="text-xs text-muted">{t("languageRegion.timezone.description")}</p>
      </div>
    </section>
  );
}

function AccessibilityTab({
  draft,
  patch,
}: {
  draft: UserSettings;
  patch: (partial: Partial<UserSettings>) => void;
}) {
  const t = useTranslations("settings");
  return (
    <section aria-labelledby="a11y-heading" className="space-y-6">
      <div>
        <h2 id="a11y-heading" className="text-lg font-semibold text-foreground">{t("accessibility.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("accessibility.description")}</p>
      </div>
      <Toggle
        checked={draft.high_contrast}
        onChange={(high_contrast) => patch({high_contrast})}
        label={t("accessibility.highContrast.label")}
        description={t("accessibility.highContrast.description")}
      />
      <Toggle
        checked={draft.screen_reader_optimized}
        onChange={(screen_reader_optimized) => patch({screen_reader_optimized})}
        label={t("accessibility.screenReaderOptimized.label")}
        description={t("accessibility.screenReaderOptimized.description")}
      />
      <Toggle
        checked={draft.keyboard_navigation}
        onChange={(keyboard_navigation) => patch({keyboard_navigation})}
        label={t("accessibility.keyboardNavigation.label")}
        description={t("accessibility.keyboardNavigation.description")}
      />
      <Toggle
        checked={draft.focus_indicator}
        onChange={(focus_indicator) => patch({focus_indicator})}
        label={t("accessibility.focusIndicator.label")}
        description={t("accessibility.focusIndicator.description")}
      />
      <Toggle
        checked={draft.dyslexia_font}
        onChange={(dyslexia_font) => patch({dyslexia_font})}
        label={t("accessibility.dyslexiaFont.label")}
        description={t("accessibility.dyslexiaFont.description")}
      />
      <Toggle
        checked={draft.reduced_motion}
        onChange={(reduced_motion) => patch({reduced_motion})}
        label={t("accessibility.reducedMotion.label")}
        description={t("accessibility.reducedMotion.description")}
      />
    </section>
  );
}

function NotificationsTab({
  draft,
  patch,
}: {
  draft: UserSettings;
  patch: (partial: Partial<UserSettings>) => void;
}) {
  const t = useTranslations("settings");
  return (
    <section aria-labelledby="notif-heading" className="space-y-6">
      <div>
        <h2 id="notif-heading" className="text-lg font-semibold text-foreground">{t("notifications.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("notifications.description")}</p>
      </div>
      <Toggle
        checked={draft.email_notifications}
        onChange={(email_notifications) => patch({email_notifications})}
        label={t("notifications.email.label")}
        description={t("notifications.email.description")}
      />
      <Toggle
        checked={draft.push_notifications}
        onChange={(push_notifications) => patch({push_notifications})}
        label={t("notifications.push.label")}
        description={t("notifications.push.description")}
      />
      <Toggle
        checked={draft.desktop_notifications}
        onChange={(desktop_notifications) => patch({desktop_notifications})}
        label={t("notifications.desktop.label")}
        description={t("notifications.desktop.description")}
      />
      <Toggle
        checked={draft.sound_notifications}
        onChange={(sound_notifications) => patch({sound_notifications})}
        label={t("notifications.sound.label")}
        description={t("notifications.sound.description")}
      />
      <div className="space-y-2">
        <label htmlFor="summary-frequency" className="text-sm font-medium text-foreground">
          {t("notifications.summaryFrequency.label")}
        </label>
        <select
          id="summary-frequency"
          value={draft.summary_frequency}
          onChange={(e) => patch({summary_frequency: e.target.value as UserSettings["summary_frequency"]})}
          className="w-full rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-foreground focus-visible:border-accent-to focus-visible:outline-none"
        >
          <option value="daily">{t("notifications.summaryFrequency.daily")}</option>
          <option value="weekly">{t("notifications.summaryFrequency.weekly")}</option>
          <option value="never">{t("notifications.summaryFrequency.never")}</option>
        </select>
        <p className="text-xs text-muted">{t("notifications.summaryFrequency.description")}</p>
      </div>
      <div className="space-y-2">
        <label htmlFor="notification-email" className="text-sm font-medium text-foreground">
          {t("notifications.notificationEmail.label")}
        </label>
        <input
          id="notification-email"
          type="email"
          value={draft.notification_email ?? ""}
          onChange={(e) => patch({notification_email: e.target.value || null})}
          placeholder={t("notifications.notificationEmail.placeholder")}
          className="w-full rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
        />
        <p className="text-xs text-muted">{t("notifications.notificationEmail.description")}</p>
      </div>
    </section>
  );
}

function PrivacyDataTab({
  draft,
  onExport,
  onDelete,
}: {
  draft: UserSettings;
  onExport: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("settings");
  return (
    <section aria-labelledby="privacy-heading" className="space-y-8">
      <div>
        <h2 id="privacy-heading" className="text-lg font-semibold text-foreground">{t("privacyData.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("privacyData.description")}</p>
      </div>
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">{t("privacyData.documents.title")}</span>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Link
            href="/privacy-policy"
            className="inline-flex items-center gap-2 rounded-lg border border-foreground/10 px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
          >
            <Shield className="h-4 w-4" aria-hidden />
            {t("privacyData.documents.privacyPolicy")}
          </Link>
          <Link
            href="/terms-of-use"
            className="inline-flex items-center gap-2 rounded-lg border border-foreground/10 px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
          >
            <AlertTriangle className="h-4 w-4" aria-hidden />
            {t("privacyData.documents.termsOfUse")}
          </Link>
        </div>
      </div>
      <div className="rounded-lg border border-foreground/10 bg-surface-raised p-4">
        <span className="text-sm font-medium text-foreground">{t("privacyData.consentHistory.title")}</span>
        <p className="mt-1 text-xs text-muted">
          {t("privacyData.consentHistory.description", {
            version: draft.terms_version ?? "—",
            date: draft.consented_at ? new Date(draft.consented_at).toLocaleDateString() : "—",
          })}
        </p>
      </div>
      <div className="rounded-lg border border-foreground/10 bg-surface-raised p-4">
        <div className="flex items-start gap-3">
          <FileDown className="mt-0.5 h-5 w-5 shrink-0 text-accent-to" aria-hidden />
          <div>
            <p className="text-sm font-medium text-foreground">{t("privacyData.exportData.title")}</p>
            <p className="mt-1 text-xs text-muted">{t("privacyData.exportData.description")}</p>
            <button
              type="button"
              onClick={onExport}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-accent-gradient px-4 py-2 text-sm font-semibold text-foreground hover:brightness-110"
            >
              <Download className="h-4 w-4" aria-hidden />
              {t("privacyData.exportData.button")}
            </button>
          </div>
        </div>
      </div>
      <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
        <div className="flex items-start gap-3">
          <Trash2 className="mt-0.5 h-5 w-5 shrink-0 text-red-500" aria-hidden />
          <div>
            <p className="text-sm font-medium text-red-500">{t("privacyData.deleteAccount.title")}</p>
            <p className="mt-1 text-xs text-muted">{t("privacyData.deleteAccount.description")}</p>
            <button
              type="button"
              onClick={onDelete}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
            >
              {t("privacyData.deleteAccount.button")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function AdvancedTab({
  draft,
  patch,
  onExport,
  onResetAll,
}: {
  draft: UserSettings;
  patch: (partial: Partial<UserSettings>) => void;
  onExport: () => void;
  onResetAll: () => void;
}) {
  const t = useTranslations("settings");
  const {toast} = useToast();
  return (
    <section aria-labelledby="advanced-heading" className="space-y-8">
      <div>
        <h2 id="advanced-heading" className="text-lg font-semibold text-foreground">{t("advanced.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("advanced.description")}</p>
      </div>
      <Toggle
        checked={draft.developer_mode}
        onChange={(developer_mode) => patch({developer_mode})}
        label={t("advanced.developerMode.label")}
        description={t("advanced.developerMode.description")}
      />
      <div className="flex items-start gap-3 rounded-lg border border-foreground/10 bg-surface-raised p-4">
        <Eraser className="mt-0.5 h-5 w-5 shrink-0 text-muted" aria-hidden />
        <div>
          <p className="text-sm font-medium text-foreground">{t("advanced.clearCache.label")}</p>
          <p className="mt-1 text-xs text-muted">{t("advanced.clearCache.description")}</p>
          <button
            type="button"
            onClick={() => {
              try {
                localStorage.clear();
                toast.success(t("advanced.clearCache.success"));
              } catch {
                toast.success(t("advanced.clearCache.success"));
              }
            }}
            className="mt-3 inline-flex items-center gap-2 rounded-lg border border-foreground/10 px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
          >
            {t("advanced.clearCache.button")}
          </button>
        </div>
      </div>
      <div className="flex items-start gap-3 rounded-lg border border-foreground/10 bg-surface-raised p-4">
        <FileDown className="mt-0.5 h-5 w-5 shrink-0 text-accent-to" aria-hidden />
        <div>
          <p className="text-sm font-medium text-foreground">{t("advanced.exportData.title")}</p>
          <p className="mt-1 text-xs text-muted">{t("advanced.exportData.description")}</p>
          <button
            type="button"
            onClick={onExport}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-accent-gradient px-4 py-2 text-sm font-semibold text-foreground hover:brightness-110"
          >
            <Download className="h-4 w-4" aria-hidden />
            {t("advanced.exportData.button")}
          </button>
        </div>
      </div>
      <div className="flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/5 p-4">
        <RotateCcw className="mt-0.5 h-5 w-5 shrink-0 text-red-500" aria-hidden />
        <div>
          <p className="text-sm font-medium text-red-500">{t("advanced.resetAllSettings.title")}</p>
          <p className="mt-1 text-xs text-muted">{t("advanced.resetAllSettings.description")}</p>
          <button
            type="button"
            onClick={onResetAll}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
          >
            {t("advanced.resetAllSettings.button")}
          </button>
        </div>
      </div>
    </section>
  );
}