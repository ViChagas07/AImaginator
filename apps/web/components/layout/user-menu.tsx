"use client";

import * as React from "react";
import {LogOut, Settings, User} from "lucide-react";
import {useTranslations} from "next-intl";
import {cn} from "@/lib/utils";
import {useAuthStore} from "@/stores/auth";
import {Link} from "@/i18n/navigation";

export function UserMenu() {
  const t = useTranslations("nav");
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const buttonRef = React.useRef<HTMLButtonElement>(null);

  const close = React.useCallback((focusBack: boolean) => {
    setOpen(false);
    if (focusBack) buttonRef.current?.focus();
  }, []);

  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        close(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open, close]);

  const name = user?.name ?? user?.email ?? "";
  const initial = name.trim().charAt(0).toUpperCase() || "?";

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={name}
        onClick={() => (open ? close(true) : setOpen(true))}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close(true);
          }
        }}
        className="flex h-9 w-9 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-foreground/15 bg-white/[0.05] text-sm font-semibold text-foreground transition-colors hover:bg-white/[0.1] focus-visible:border-accent-to focus-visible:outline-none"
      >
        {user?.avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.avatarUrl}
            alt={name}
            referrerPolicy="no-referrer"
            className="h-full w-full object-cover"
          />
        ) : (
          <span aria-hidden>{initial}</span>
        )}
      </button>

      <div
        role="menu"
        aria-label={name}
        className={cn(
          "absolute end-0 top-full z-50 mt-2 min-w-[260px] overflow-hidden rounded-xl border border-foreground/10 bg-surface-raised shadow-2xl",
          "origin-top-right transition-all duration-200 ease-out",
          open
            ? "translate-y-0 opacity-100"
            : "pointer-events-none -translate-y-1 opacity-0",
        )}
      >
        <div className="border-b border-foreground/10 px-4 py-3">
          <p className="truncate text-sm font-medium text-foreground">{user?.name}</p>
          <p className="truncate text-xs text-muted">{user?.email}</p>
          <span className="mt-1.5 inline-flex items-center rounded-full bg-accent-gradient/20 px-2 py-0.5 text-xs font-medium text-accent-to">
            {t("account.tierFree")}
          </span>
        </div>
        <Link
          href="/minha-conta"
          onClick={() => close(false)}
          role="menuitem"
          className="flex cursor-pointer items-center gap-2 px-4 py-2.5 text-start text-sm text-muted transition-colors hover:bg-white/[0.05] hover:text-foreground"
        >
          <User className="h-4 w-4" aria-hidden />
          <div className="flex flex-col">
            <span>{t("account.myAccount")}</span>
            <span className="text-xs text-muted-foreground">{t("account.myAccountSubtitle")}</span>
          </div>
        </Link>
        <Link
          href="/configuracoes"
          onClick={() => close(false)}
          role="menuitem"
          className="flex cursor-pointer items-center gap-2 px-4 py-2.5 text-start text-sm text-muted transition-colors hover:bg-white/[0.05] hover:text-foreground"
        >
          <Settings className="h-4 w-4" aria-hidden />
          {t("account.settings")}
        </Link>
        <div className="border-t border-foreground/10 my-1" />
        <button
          type="button"
          onClick={() => {
            close(false);
            logout();
          }}
          role="menuitem"
          className="flex w-full cursor-pointer items-center gap-2 px-4 py-2.5 text-start text-sm text-muted transition-colors hover:bg-white/[0.05] hover:text-foreground"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          {t("logout")}
        </button>
      </div>
    </div>
  );
}
