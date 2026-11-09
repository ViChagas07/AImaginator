"use client";

import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";

import {getAccessToken} from "@/lib/auth-token";
import {API_BASE_URL} from "@/lib/constants";

type FlaggedUser = {
  id: string;
  handle: string | null;
  plan: string;
  moderation_flag: boolean;
  blocked_until: string | null;
  generation_credits: number;
};

export function AdminConsole() {
  const t = useTranslations("admin");
  const [token] = useState(() =>
    typeof window === "undefined" ? null : getAccessToken(),
  );
  const [users, setUsers] = useState<FlaggedUser[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE_URL}/api/v1/admin/users/flagged`, {
      headers: {Authorization: `Bearer ${token}`},
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error("forbidden");
        return response.json();
      })
      .then(setUsers)
      .catch(() => setError(true));
  }, [token]);

  if (!token || error) {
    return <p className="text-sm text-red-600">{t("unauthorized")}</p>;
  }
  if (users === null) {
    return <p className="text-sm text-muted-foreground">…</p>;
  }
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">{t("flaggedUsers")}</h2>
      {users.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noUsers")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="py-2">ID</th>
                <th className="py-2">plan</th>
                <th className="py-2">credits</th>
                <th className="py-2">blocked</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b">
                  <td className="py-2 font-mono text-xs">{user.id}</td>
                  <td className="py-2">{user.plan}</td>
                  <td className="py-2">{user.generation_credits}</td>
                  <td className="py-2">{user.blocked_until ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
