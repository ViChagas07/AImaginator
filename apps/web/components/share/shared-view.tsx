"use client";

import {useEffect, useState} from "react";

import {ReportButton} from "@/components/share/report-button";
import {API_BASE_URL} from "@/lib/constants";

type Shared = {
  imageUrl: string;
  title: string | null;
  createdAt: string;
  prompt?: string;
};

export function SharedView({token}: {token: string}) {
  const [data, setData] = useState<Shared | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/public/shares/${encodeURIComponent(token)}`, {
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error("missing");
        return response.json();
      })
      .then(setData)
      .catch(() => setMissing(true));
  }, [token]);

  if (missing) {
    return <p className="text-sm text-muted">Link indisponivel.</p>;
  }
  if (!data) return <p className="text-sm text-muted">…</p>;
  return (
    <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={data.imageUrl}
        alt={data.title ?? "AImaginator"}
        className="w-full rounded-xl border border-foreground/10"
      />
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">
          {data.title ?? new Date(data.createdAt).toLocaleDateString()}
        </p>
        <ReportButton token={token} />
      </div>
      {data.prompt ? (
        <p className="mt-4 whitespace-pre-wrap text-sm text-muted">{data.prompt}</p>
      ) : null}
    </main>
  );
}
