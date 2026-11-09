"use client";

import {useState} from "react";
import {useTranslations} from "next-intl";

import {API_BASE_URL} from "@/lib/constants";

export function ReportButton({token}: {token: string}) {
  const t = useTranslations("share");
  const [reason, setReason] = useState("other");
  const [sent, setSent] = useState(false);

  if (sent) return <p className="text-xs text-muted">{t("reportSent")}</p>;
  return (
    <form
      className="flex flex-wrap items-center gap-2 text-xs"
      onSubmit={async (event) => {
        event.preventDefault();
        await fetch(`${API_BASE_URL}/api/v1/public/shares/${encodeURIComponent(token)}/reports`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({
            reason,
          }),
        }).catch(() => undefined);
        setSent(true);
      }}
    >
      <label htmlFor="report-reason" className="sr-only">
        {t("reportReason")}
      </label>
      <select
        id="report-reason"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        className="rounded border border-foreground/20 bg-canvas px-2 py-1"
      >
        <option value="nsfw">{t("reasons.nsfw")}</option>
        <option value="gore">{t("reasons.gore")}</option>
        <option value="hate">{t("reasons.hate")}</option>
        <option value="self_harm">{t("reasons.self_harm")}</option>
        <option value="other">{t("reasons.other")}</option>
      </select>
      <button
        type="submit"
        className="rounded border border-foreground/20 px-2 py-1 hover:bg-surface-raised"
      >
        {t("report")}
      </button>
    </form>
  );
}
