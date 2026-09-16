"use client";

import {useEffect} from "react";
import {useTranslations} from "next-intl";
import {Link} from "@/i18n/navigation";
import {useAuthStore} from "@/stores/auth";

export function AuthButton() {
  const t = useTranslations("nav");
  const status = useAuthStore((s) => s.status);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    if (status !== "unknown") return;
    void fetchMe();
  }, [status, fetchMe]);

  if (status !== "unauthenticated") return null;

  return (
    <Link
      href="/login"
      className="rounded-md bg-surface-raised px-4 py-2 text-sm text-foreground"
    >
      {t("login")}
    </Link>
  );
}