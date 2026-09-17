import type {Metadata} from "next";
import {getTranslations} from "next-intl/server";
import {GalleryList} from "@/components/gallery/gallery-list";
import {API_BASE_URL, SITE_URL} from "@/lib/constants";
import {languageAlternates} from "@/lib/i18n";
import type {GalleryItem} from "@/stores/gallery";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/gallery">): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations("gallery");
  const canonical = `${SITE_URL}/${locale}/gallery`;

  let latest: GalleryItem[] = [];
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/gallery/public`, {
      next: {revalidate: 60},
    });
    if (res.ok) {
      const data = (await res.json()) as {items?: GalleryItem[]};
      latest = data.items ?? [];
    }
  } catch {
    // API indisponível — manter metadados base.
  }

  const ogImages =
    latest.length > 0
      ? latest.slice(0, 4).map((item) => ({url: item.imageUrl}))
      : undefined;

  return {
    title: t("title"),
    description: t("description"),
    alternates: {
      canonical,
      languages: languageAlternates("/gallery"),
    },
    openGraph: {
      title: t("title"),
      description: t("description"),
      url: canonical,
      siteName: "AImaginator",
      images: ogImages,
    },
    twitter: {
      card: "summary_large_image",
      title: t("title"),
      description: t("description"),
      images: ogImages?.map((image) => image.url),
    },
  };
}

export const revalidate = 60;

async function fetchInitialGallery(): Promise<{
  items: GalleryItem[];
  cursor: string | null;
}> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/gallery/public`, {
      next: {revalidate: 60},
    });
    if (!res.ok) return {items: [], cursor: null};
    return (await res.json()) as {items: GalleryItem[]; cursor: string | null};
  } catch {
    return {items: [], cursor: null};
  }
}

export default async function GalleryPage() {
  const t = await getTranslations("gallery");
  const {items, cursor} = await fetchInitialGallery();

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-semibold tracking-tight text-foreground">
        {t("title")}
      </h1>
      <p className="mb-10 mt-2 max-w-2xl text-muted">{t("description")}</p>
      <GalleryList initialItems={items} initialCursor={cursor} />
    </div>
  );
}
