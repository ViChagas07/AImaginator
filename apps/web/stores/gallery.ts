import {create} from "zustand";

export type GalleryItem = {
  id: string;
  imageUrl: string;
  prompt: string;
  author: string | null;
  createdAt: string;
};

type GalleryState = {
  items: GalleryItem[];
  cursor: string | null;
  hasMore: boolean;
  loading: boolean;
  loadMore: () => Promise<void>;
  hydrate: (items: GalleryItem[], cursor: string | null) => void;
};

export const useGalleryStore = create<GalleryState>((set, get) => ({
  items: [],
  cursor: null,
  hasMore: false,
  loading: false,

  hydrate: (items, cursor) => set({items, cursor, hasMore: cursor !== null}),

  async loadMore() {
    const {cursor, loading} = get();
    if (loading || cursor === null) return;
    set({loading: true});
    try {
      const res = await fetch(
        `/api/gallery?cursor=${encodeURIComponent(cursor)}`,
      );
      if (res.ok) {
        const data = (await res.json()) as {
          items: GalleryItem[];
          cursor: string | null;
        };
        set({
          items: [...get().items, ...data.items],
          cursor: data.cursor,
          hasMore: data.cursor !== null,
        });
      }
    } finally {
      set({loading: false});
    }
  },
}));
