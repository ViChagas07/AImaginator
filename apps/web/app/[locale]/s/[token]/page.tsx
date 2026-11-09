import type {Metadata} from "next";

import {SharedView} from "@/components/share/shared-view";
import {API_BASE_URL} from "@/lib/constants";

type Shared = {
  imageUrl: string;
  title: string | null;
  createdAt: string;
  prompt?: string;
};

async function load(token: string): Promise<Shared | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/public/shares/${encodeURIComponent(token)}`,
    {cache: "no-store"},
  ).catch(() => null);
  if (!response?.ok) return null;
  return response.json();
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{locale: string; token: string}>;
}): Promise<Metadata> {
  const {token} = await params;
  const data = await load(token);
  if (!data) return {title: "AImaginator", robots: {index: false}};
  return {
    title: data.title ?? "AImaginator",
    description: "Imagem criada com AImaginator.",
    robots: {index: false},
    openGraph: {
      title: data.title ?? "AImaginator",
      images: [{url: data.imageUrl}],
      type: "website",
    },
    twitter: {card: "summary_large_image", images: [data.imageUrl]},
  };
}

export default async function SharedPage({
  params,
}: {
  params: Promise<{locale: string; token: string}>;
}) {
  const {token} = await params;
  return <SharedView token={token} />;
}
