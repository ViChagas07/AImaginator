"use client";

import {useEffect} from "react";
import {useTranslations} from "next-intl";
import {Link} from "@/i18n/navigation";
import {useAuthStore} from "@/stores/auth";
import {UserMenu} from "@/components/layout/user-menu";

export function AuthButton() {
  const t = useTranslations("nav");
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    if (status !== "unknown") return;
    void fetchMe();
  }, [status, fetchMe]);

  if (status === "authenticated" && user) return <UserMenu />;

  return (
    <Link
      href="/login"
      className="bg-cta-gradient inline-flex items-center whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-semibold text-white transition-all duration-200 hover:scale-[1.03] hover:brightness-110 sm:px-4 sm:py-2 sm:text-sm"
      style={{textShadow: "0 1px 3px rgba(0, 0, 0, 0.35)"}}
    >
      {t("login")}
    </Link>
  );
}
