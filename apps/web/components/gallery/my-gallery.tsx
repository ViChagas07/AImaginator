"use client";

import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";
import {Check, Loader2, Pencil, Trash2, X} from "lucide-react";
import {useAuthStore} from "@/stores/auth";
import {useMyGalleryStore} from "@/stores/my-gallery";

export function MyGallery() {
  const t = useTranslations("gallery");
  const status = useAuthStore((s) => s.status);
  const gallery = useMyGalleryStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");

  useEffect(() => {
    if (status === "authenticated" && !gallery.loaded) void gallery.load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  if (status !== "authenticated") return null;

  function startRename(id: string, current: string | null) {
    setEditingId(id);
    setDraftTitle(current ?? "");
  }

  async function commitRename(id: string) {
    const title = draftTitle.trim();
    if (!title) return;
    await gallery.rename(id, title);
    setEditingId(null);
  }

  function confirmDelete(id: string) {
    if (window.confirm(t("deleteConfirm"))) void gallery.remove(id);
  }

  return (
    <section aria-labelledby="my-arts-heading" className="mb-10">
      <h2 id="my-arts-heading" className="mb-4 text-2xl font-semibold tracking-tight text-foreground">
        {t("myArtsTitle")}
      </h2>
      {!gallery.loaded && gallery.loading ? (
        <p className="text-sm text-muted">{t("loadingMyArts")}</p>
      ) : gallery.items.length === 0 ? (
        <p className="text-sm text-muted">{t("myArtsEmpty")}</p>
      ) : (
        <GalleryGrid
          items={gallery.items}
          cursor={gallery.cursor}
          loading={gallery.loading}
          editingId={editingId}
          draftTitle={draftTitle}
          setDraftTitle={setDraftTitle}
          startRename={startRename}
          commitRename={commitRename}
          cancelRename={() => setEditingId(null)}
          confirmDelete={confirmDelete}
          loadMore={() => void gallery.loadMore()}
        />
      )}
    </section>
  );
}

function GalleryGrid({
  items,
  cursor,
  loading,
  editingId,
  draftTitle,
  setDraftTitle,
  startRename,
  commitRename,
  cancelRename,
  confirmDelete,
  loadMore,
}: {
  items: {id: string; imageUrl: string | null; prompt: string; title: string | null; status: string}[];
  cursor: string | null;
  loading: boolean;
  editingId: string | null;
  draftTitle: string;
  setDraftTitle: (v: string) => void;
  startRename: (id: string, current: string | null) => void;
  commitRename: (id: string) => void;
  cancelRename: () => void;
  confirmDelete: (id: string) => void;
  loadMore: () => void;
}) {
  const t = useTranslations("gallery");
  return (
    <>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((item) => (
          <li
            key={item.id}
            className="overflow-hidden rounded-lg border border-foreground/10 bg-surface"
          >
            {item.imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={item.imageUrl}
                alt={item.title ?? item.prompt}
                loading="lazy"
                className="aspect-square w-full object-cover"
              />
            ) : (
              <div className="flex aspect-square w-full items-center justify-center bg-surface-raised text-xs text-muted">
                {item.status}
              </div>
            )}
            <div className="space-y-2 p-3">
              {editingId === item.id ? (
                <div className="flex items-center gap-1">
                  <input
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    aria-label={t("renameLabel")}
                    className="min-w-0 flex-1 rounded border border-foreground/10 bg-transparent px-2 py-1 text-xs text-foreground focus-visible:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => commitRename(item.id)}
                    aria-label={t("saveRename")}
                    className="text-muted hover:text-foreground"
                  >
                    <Check className="h-4 w-4" aria-hidden />
                  </button>
                  <button
                    type="button"
                    onClick={cancelRename}
                    aria-label={t("cancelRename")}
                    className="text-muted hover:text-foreground"
                  >
                    <X className="h-4 w-4" aria-hidden />
                  </button>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 text-xs text-muted">
                    {item.title ?? item.prompt}
                  </p>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => startRename(item.id, item.title)}
                      aria-label={t("rename")}
                      title={t("rename")}
                      className="text-muted hover:text-foreground"
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden />
                    </button>
                    <button
                      type="button"
                      onClick={() => confirmDelete(item.id)}
                      aria-label={t("delete")}
                      title={t("delete")}
                      className="text-muted hover:text-foreground"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
      {cursor !== null && (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md bg-surface-raised px-4 py-2 text-sm text-foreground disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            {t("loadMore")}
          </button>
        </div>
      )}
    </>
  );
}
