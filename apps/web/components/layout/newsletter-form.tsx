"use client";

import {useState} from "react";
import {useTranslations} from "next-intl";
import {Check, Mail} from "lucide-react";

export function NewsletterForm() {
  const t = useTranslations("footer");
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    setDone(true);
    setEmail("");
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Mail
            className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden
          />
          <input
            id="newsletter-email"
            name="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setDone(false);
            }}
            placeholder={t("newsletterPlaceholder")}
            aria-label={t("newsletterLabel")}
            className="h-11 w-full rounded-full border border-foreground/10 bg-surface-raised pl-11 pr-4 text-sm text-foreground placeholder:text-muted focus-visible:border-accent-to focus-visible:outline-none"
          />
        </div>
        <button
          type="submit"
          className="bg-accent-gradient inline-flex h-11 shrink-0 items-center rounded-full px-5 text-sm font-semibold text-foreground disabled:opacity-50"
        >
          {t("newsletterButton")}
        </button>
      </div>
      {done ? (
        <p
          role="status"
          className="flex items-center gap-1.5 text-sm text-foreground"
        >
          <Check className="h-4 w-4" aria-hidden />
          {t("newsletterSuccess")}
        </p>
      ) : null}
    </form>
  );
}
