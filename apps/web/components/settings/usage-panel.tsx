"use client";

import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";

import {getAccessToken} from "@/lib/auth-token";
import {API_BASE_URL} from "@/lib/constants";

type Usage = {
  plan: string;
  generation_credits: number;
  period_start: string;
  daily_prompts_total: number;
  daily_prompts_remaining: number;
  upscale_limit: number;
  upscale_remaining: number;
};

export function UsagePanel() {
  const t = useTranslations("usage");
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetch(`${API_BASE_URL}/api/v1/users/me/usage`, {
      headers: {Authorization: `Bearer ${token}`},
      cache: "no-store",
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => setUsage(data))
      .catch(() => undefined);
  }, []);

  if (!usage) return null;
  return (
    <section className="mb-8 rounded-xl border border-foreground/10 bg-surface-raised p-4">
      <h2 className="text-sm font-semibold text-foreground">{t("title")}</h2>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted">{t("balance")}</dt>
          <dd className="font-semibold">{usage.generation_credits}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("plan")}</dt>
          <dd className="font-semibold">{usage.plan}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("daily")}</dt>
          <dd className="font-semibold">
            {usage.daily_prompts_remaining}/{usage.daily_prompts_total}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("upscale")}</dt>
          <dd className="font-semibold">
            {usage.upscale_remaining}/{usage.upscale_limit}
          </dd>
        </div>
      </dl>
    </section>
  );
}
