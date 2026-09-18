import {create} from "zustand";
import {API_BASE_URL} from "@/lib/constants";
import {authedFetch} from "@/lib/api";

export type MyArt = {
  id: string;
  imageUrl: string | null;
  prompt: string;
  title: string | null;
  status: string;
  createdAt: string;
};

type MyGalleryState = {
  items: MyArt[];
  cursor: string | null;
  loading: boolean;
  loaded: boolean;
  load: () => Promise<void>;
  loadMore: () => Promise<void>;
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
};

type MyGalleryPage = {
  items: MyArt[];
  cursor: string | null;
};

export const useMyGalleryStore = create<MyGalleryState>((set, get) => ({
  items: [],
  cursor: null,
  loading: false,
  loaded: false,

  async load() {
    set({loading: true});
    try {
      const res = await authedFetch(`${API_BASE_URL}/api/v1/gallery/me`, {
        cache: "no-store",
      });
      if (res.ok) {
        const data = (await res.json()) as MyGalleryPage;
        set({items: data.items, cursor: data.cursor, loaded: true});
      }
    } finally {
      set({loading: false});
    }
  },

  async loadMore() {
    const {cursor, loading} = get();
    if (loading || cursor === null) return;
    set({loading: true});
    try {
      const res = await authedFetch(
        `${API_BASE_URL}/api/v1/gallery/me?cursor=${encodeURIComponent(cursor)}`,
        {cache: "no-store"},
      );
      if (res.ok) {
        const data = (await res.json()) as MyGalleryPage;
        set({
          items: [...get().items, ...data.items],
          cursor: data.cursor,
        });
      }
    } finally {
      set({loading: false});
    }
  },

  async rename(id, title) {
    const res = await authedFetch(`${API_BASE_URL}/api/v1/gallery/me/${id}`, {
      method: "PATCH",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({title}),
    });
    if (!res.ok) return;
    const updated = (await res.json()) as MyArt;
    set({
      items: get().items.map((item) => (item.id === id ? updated : item)),
    });
  },

  async remove(id) {
    const res = await authedFetch(`${API_BASE_URL}/api/v1/gallery/me/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) return;
    set({items: get().items.filter((item) => item.id !== id)});
  },
}));
