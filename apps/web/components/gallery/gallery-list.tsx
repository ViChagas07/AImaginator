"use client";

import {useEffect} from "react";
import {useTranslations} from "next-intl";
import {Loader2} from "lucide-react";
import {useGalleryStore, type GalleryItem} from "@/stores/gallery";

export function GalleryList({
  initialItems,
  initialCursor,
}: {
  initialItems: GalleryItem[];
  initialCursor: string | null;
}) {
  const t = useTranslations("gallery");
  const gallery = useGalleryStore();

  useEffect(() => {
    gallery.hydrate(initialItems, initialCursor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (gallery.items.length === 0) {
    return <p className="text-muted">{t("empty")}</p>;
  }

  return (
    <>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {gallery.items.map((item) => (
          <li
            key={item.id}
            className="overflow-hidden rounded-lg border border-foreground/10 bg-surface"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={item.imageUrl}
              alt={item.prompt}
              loading="lazy"
              className="aspect-square w-full object-cover"
            />
            <div className="p-3">
              <p className="line-clamp-2 text-xs text-muted">{item.prompt}</p>
              {item.author && (
                <p className="mt-1 text-xs text-foreground/70">
                  {t("by")} {item.author}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
      {gallery.hasMore && (
        <button
          type="button"
          onClick={() => void gallery.loadMore()}
          disabled={gallery.loading}
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-surface-raised px-4 py-2 text-sm text-foreground disabled:opacity-50"
        >
          {gallery.loading && (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          )}
          {t("loadMore")}
        </button>
      )}
    </>
  );
}
