import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";

import {AdminConsole} from "@/components/admin/admin-console";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/admin">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations({locale, namespace: "admin"});
  return {title: t("title"), robots: {index: false}};
}

export default async function AdminPage() {
  const t = await getTranslations("admin");
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="mb-8 text-3xl font-semibold tracking-tight">{t("title")}</h1>
      <AdminConsole />
    </div>
  );
}
