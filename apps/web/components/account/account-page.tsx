"use client";

import * as React from "react";
import {useState, useCallback, useEffect} from "react";
import {Camera, Trash2, Save, X, Loader2} from "lucide-react";
import {useTranslations} from "next-intl";
import {useAuthStore} from "@/stores/auth";
import {useAccountStore} from "@/stores/account";
import {ImageCropper} from "@/components/ui/image-cropper";
import {useToast} from "@/components/ui/toast";
import {cn} from "@/lib/utils";

function ProfilePhotoSection({user}: {user: {name: string; email: string; avatarUrl: string | null}}) {
  const t = useTranslations("account");
  const {uploadAvatar, removeAvatar, loading} = useAccountStore();
  const {toast} = useToast();
  const [showCropper, setShowCropper] = useState<string | null>(null);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      toast.error(t("profilePhoto.fileTypes"));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error(t("profilePhoto.fileTypes"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setShowCropper(reader.result as string);
    reader.readAsDataURL(file);
  }, [toast, t]);

  const handleCropComplete = async (croppedDataUrl: string) => {
    setShowCropper(null);
    try {
      const res = await fetch(croppedDataUrl);
      const blob = await res.blob();
      const file = new File([blob], "avatar.jpg", {type: "image/jpeg"});
      await uploadAvatar(file);
      void useAuthStore.getState().fetchMe();
      toast.success(t("profilePhoto.changePhoto"));
    } catch {
      toast.error(t("personalInfo.error"));
    }
  };

  const handleRemoveAvatar = async () => {
    if (!window.confirm(t("profilePhoto.removePhoto"))) return;
    try {
      await removeAvatar();
      void useAuthStore.getState().fetchMe();
      toast.success(t("profilePhoto.removePhoto"));
    } catch {
      toast.error(t("personalInfo.error"));
    }
  };

  const initial = user.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <section aria-labelledby="profile-photo-heading" className="space-y-6">
      <h2 id="profile-photo-heading" className="text-xl font-semibold text-foreground">
        {t("sections.profilePhoto")}
      </h2>
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
        <div className="relative">
          {user.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.avatarUrl}
              alt={user.name}
              className="h-32 w-32 rounded-full object-cover border border-foreground/10"
            />
          ) : (
            <div className="flex h-32 w-32 items-center justify-center rounded-full border border-foreground/10 bg-surface-raised text-4xl font-semibold text-foreground">
              {initial}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-2 w-full sm:w-auto">
          <label className="cursor-pointer">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileSelect}
              className="sr-only"
              disabled={loading}
            />
            <button
              type="button"
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground bg-surface-raised border border-foreground/10 rounded-lg hover:bg-surface hover:border-accent-to transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Camera className="h-4 w-4" aria-hidden />
              {loading ? t("profilePhoto.uploading") : t("profilePhoto.changePhoto")}
            </button>
          </label>
          {user.avatarUrl && (
            <button
              type="button"
              onClick={handleRemoveAvatar}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              {t("profilePhoto.removePhoto")}
            </button>
          )}
          <p className="text-xs text-muted">{t("profilePhoto.fileTypes")}</p>
        </div>
      </div>
      {showCropper && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="bg-surface rounded-xl p-4 w-full max-w-md max-h-[90vh] overflow-auto">
            <h3 className="mb-4 text-lg font-semibold">{t("profilePhoto.cropHint")}</h3>
            <ImageCropper
              src={showCropper}
              onComplete={handleCropComplete}
              onCancel={() => setShowCropper(null)}
              cancelLabel={t("profilePhoto.cancel")}
              applyLabel={t("profilePhoto.apply")}
            />
          </div>
        </div>
      )}
    </section>
  );
}

function PersonalInfoSection({user}: {user: {id: string; name: string; email: string; googleSub: string | null; bio: string | null; handle: string | null}}) {
  const t = useTranslations("account");
  const {updateProfile} = useAccountStore();
  const {toast} = useToast();
  const [formData, setFormData] = useState({
    name: user.name,
    bio: user.bio ?? "",
    handle: user.handle ?? "",
  });
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({...prev, [field]: value}));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateProfile({
        name: formData.name,
        bio: formData.bio || undefined,
        handle: formData.handle || undefined,
      });
      void useAuthStore.getState().fetchMe();
      toast.success(t("personalInfo.saved"));
      setDirty(false);
    } catch {
      toast.error(t("personalInfo.error"));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      name: user.name,
      bio: user.bio ?? "",
      handle: user.handle ?? "",
    });
    setDirty(false);
  };

  return (
    <section aria-labelledby="personal-info-heading" className="space-y-6">
      <h2 id="personal-info-heading" className="text-xl font-semibold text-foreground">
        {t("sections.personalInfo")}
      </h2>
      <div className="space-y-4">
        <div className="grid gap-2">
          <label htmlFor="fullName" className="text-sm font-medium text-foreground">
            {t("personalInfo.fullName")}
          </label>
          <input
            id="fullName"
            type="text"
            value={formData.name}
            onChange={(e) => handleChange("name", e.target.value)}
            placeholder={t("personalInfo.fullNamePlaceholder")}
            className="w-full rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
            maxLength={200}
            required
          />
        </div>
        <div className="grid gap-2">
          <label className="text-sm font-medium text-foreground">{t("personalInfo.email")}</label>
          <div className="flex items-center gap-2">
            <input
              type="email"
              value={user.email}
              readOnly
              className="flex-1 rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-muted"
            />
            {user.googleSub && (
              <span className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-500">
                {t("personalInfo.emailGoogleBadge")}
              </span>
            )}
          </div>
        </div>
        <div className="grid gap-2">
          <label htmlFor="bio" className="text-sm font-medium text-foreground">
            {t("personalInfo.bio")}
          </label>
          <textarea
            id="bio"
            value={formData.bio}
            onChange={(e) => handleChange("bio", e.target.value)}
            placeholder={t("personalInfo.bioPlaceholder")}
            rows={3}
            maxLength={160}
            className="w-full rounded-lg border border-foreground/10 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
          />
          <p className="text-xs text-muted text-right">
            {t("personalInfo.bioCharCount", {count: formData.bio.length})}
          </p>
        </div>
        <div className="grid gap-2">
          <label htmlFor="handle" className="text-sm font-medium text-foreground">
            {t("personalInfo.handle")}
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">@</span>
            <input
              id="handle"
              type="text"
              value={formData.handle}
              onChange={(e) => handleChange("handle", e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
              placeholder={t("personalInfo.handlePlaceholder")}
              className="w-full rounded-lg border border-foreground/10 bg-surface pl-8 pr-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
              maxLength={50}
              pattern="^[a-zA-Z0-9_-]+$"
            />
          </div>
          <p className="text-xs text-muted">{t("personalInfo.handleHint")}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 pt-4 border-t border-foreground/10">
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || saving}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground bg-accent-gradient rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {t("personalInfo.saving")}
            </>
          ) : (
            <>
              <Save className="h-4 w-4" aria-hidden />
              {t("personalInfo.save")}
            </>
          )}
        </button>
        {dirty && (
          <button
            type="button"
            onClick={handleCancel}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-muted bg-surface-raised border border-foreground/10 rounded-lg hover:bg-surface hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" aria-hidden />
            {t("personalInfo.cancel")}
          </button>
        )}
      </div>
    </section>
  );
}

function AccountStatsSection({stats}: {stats: {accountCreatedAt: string; totalGenerations: number; totalSavedArts: number; currentTier: string; creditsUsedThisPeriod: number; creditsLimit: number} | null}) {
  const t = useTranslations("account");

  if (!stats) return null;

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("pt-BR", {day: "2-digit", month: "long", year: "numeric"});
    } catch {
      return dateStr;
    }
  };

  return (
    <section aria-labelledby="account-stats-heading" className="space-y-6">
      <h2 id="account-stats-heading" className="text-xl font-semibold text-foreground">
        {t("sections.accountStats")}
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label={t("accountStats.accountCreated")} value={formatDate(stats.accountCreatedAt)} />
        <StatCard label={t("accountStats.totalGenerations")} value={stats.totalGenerations.toLocaleString()} />
        <StatCard label={t("accountStats.totalSavedArts")} value={stats.totalSavedArts.toLocaleString()} />
      </div>
    </section>
  );
}

function StatCard({label, value}: {label: string; value: string | number}) {
  return (
    <div className="rounded-xl border border-foreground/10 bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function ConnectedProvidersSection({providers}: {providers: {name: string; connected: boolean; email: string | null}[]}) {
  const t = useTranslations("account");
  const {toast} = useToast();
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const handleDisconnect = async (providerName: string) => {
    if (!window.confirm(t("connectedProviders.disconnectConfirm"))) return;
    setDisconnecting(providerName);
    try {
      // TODO: implementar chamada à API
      toast.warning(t("connectedProviders.cannotDisconnectOnly"));
    } finally {
      setDisconnecting(null);
    }
  };

  return (
    <section aria-labelledby="connected-providers-heading" className="space-y-6">
      <h2 id="connected-providers-heading" className="text-xl font-semibold text-foreground">
        {t("sections.connectedProviders")}
      </h2>
      {providers.length === 0 ? (
        <p className="text-muted">{t("connectedProviders.none")}</p>
      ) : (
        <div className="space-y-3">
          {providers.map((provider) => (
            <div
              key={provider.name}
              className="flex items-center justify-between p-4 rounded-xl border border-foreground/10 bg-surface"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-gradient/20">
                  {provider.name === "Google" && (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      />
                    </svg>
                  )}
                </div>
                <div>
                  <p className="font-medium text-foreground">{provider.name}</p>
                  {provider.email && <p className="text-sm text-muted">{provider.email}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                  provider.connected
                    ? "bg-green-500/10 text-green-500"
                    : "bg-muted text-muted"
                )}>
                  {provider.connected ? t("connectedProviders.connected") : "Desconectado"}
                </span>
                {provider.connected && (
                  <button
                    type="button"
                    onClick={() => handleDisconnect(provider.name)}
                    disabled={disconnecting === provider.name}
                    className="text-red-500 hover:text-red-400 text-sm font-medium disabled:opacity-50"
                  >
                    {disconnecting === provider.name ? "..." : t("connectedProviders.disconnect")}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function AccountPage() {
  const t = useTranslations("account");
  const user = useAuthStore((s) => s.user);
  const {fetchStats, fetchProviders, stats, providers} = useAccountStore();

  useEffect(() => {
    if (user) {
      void fetchStats();
      void fetchProviders();
    }
  }, [user, fetchStats, fetchProviders]);

  if (!user) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 text-center">
        <p className="text-muted">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-2 text-muted">{t("subtitle")}</p>
      </div>

      <div className="space-y-8">
        <ProfilePhotoSection user={{name: user.name, email: user.email, avatarUrl: user.avatarUrl}} />
        <PersonalInfoSection
          user={{
            id: user.id,
            name: user.name,
            email: user.email,
            googleSub: user.googleSub ?? null,
            bio: user.bio ?? null,
            handle: user.handle ?? null,
          }}
        />
        <AccountStatsSection stats={stats} />
        <ConnectedProvidersSection providers={providers} />
      </div>
    </div>
  );
}