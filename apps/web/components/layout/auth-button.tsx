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

  if (status === "authenticated") return null;

  return (
    <Link
      href="/login"
      className="bg-cta-gradient inline-flex items-center rounded-md px-4 py-2 text-sm font-semibold text-white transition-all duration-200 hover:scale-[1.03] hover:brightness-110"
      style={{textShadow: "0 1px 3px rgba(0, 0, 0, 0.35)"}}
    >
      {t("login")}
    </Link>
  );
}