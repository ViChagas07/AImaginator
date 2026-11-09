"use client";

import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";

import {API_BASE_URL} from "@/lib/constants";

type Status = {
  maintenance: boolean;
  available: Record<string, boolean>;
};

export function StatusBanner() {
  const t = useTranslations("status");
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/v1/status`, {cache: "no-store"})
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data) setStatus(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status) return null;
  const offline = Object.values(status.available ?? {}).some((value) => !value);
  if (!status.maintenance && !offline) return null;
  return (
    <div
      role="status"
      className="mb-6 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
    >
      {status.maintenance ? t("maintenance") : t("offline")}
    </div>
  );
}
