"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { cn } from "@/lib/utils";

type Verse = {
  reference: string;
  text: string;
};

const FAMOUS_REFERENCES = [
  "João 3:16",
  "Salmos 23:1",
  "Filipenses 4:13",
  "Romanos 8:28",
  "Provérbios 3:5-6",
  "Josué 1:9",
  "Jeremias 29:11",
  "Mateus 6:33",
  "Gênesis 1:1",
  "Isaías 41:10",
  "1 Coríntios 13:4-7",
  "Salmos 46:1",
  "Romanos 12:2",
  "Gálatas 5:22-23",
  "Apocalipse 21:4",
  "Salmos 91:1",
  "Isaías 40:31",
  "Mateus 11:28",
  "João 14:6",
  "Romanos 5:8",
  "Efésios 2:8-9",
  "Salmos 118:24",
  "1 Pedro 5:7",
  "2 Timóteo 1:7",
  "Hebreus 11:1",
  "Miqueias 6:8",
  "Salmos 139:14",
  "Lamentações 3:22-23",
];

const FALLBACK_VERSES: Record<string, Verse> = {
  almeida: {
    reference: "João 3:16",
    text: "Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito, para que todo aquele que nele crê não pereça, mas tenha a vida eterna.",
  },
  kjv: {
    reference: "John 3:16",
    text: "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
  },
};

const DEFAULT_TRANSLATION = "almeida";
const REQUEST_TIMEOUT_MS = 3000;
const CACHE_PREFIX = "aimaginator.bibleVerse.";

function translationForLocale(locale: string): string {
  return locale === "pt-BR" ? "almeida" : "kjv";
}

function fallbackFor(translation: string): Verse {
  return FALLBACK_VERSES[translation] ?? FALLBACK_VERSES[DEFAULT_TRANSLATION];
}

function pickRandomReference(): string {
  const index = Math.floor(Math.random() * FAMOUS_REFERENCES.length);
  return FAMOUS_REFERENCES[index];
}

function readCache(cacheKey: string): Verse | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(cacheKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Verse;
    if (
      parsed &&
      typeof parsed.text === "string" &&
      typeof parsed.reference === "string"
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

function writeCache(cacheKey: string, verse: Verse): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(cacheKey, JSON.stringify(verse));
  } catch {
    // Ignore privacy/quota errors; the verse is still shown in-memory.
  }
}

async function fetchVerse(
  reference: string,
  translation: string,
  signal: AbortSignal,
): Promise<Verse> {
  const url = `https://bible-api.com/${encodeURIComponent(reference)}?translation=${translation}`;
  const response = await fetch(url, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`bible-api responded with ${response.status}`);
  }
  const data = (await response.json()) as { text?: string; reference?: string };
  if (!data.text || !data.reference) {
    throw new Error("Unexpected bible-api payload");
  }
  return {
    text: data.text.replace(/\s+/g, " ").trim(),
    reference: data.reference,
  };
}

export function RandomBibleVerse({ className }: { className?: string }) {
  const locale = useLocale();
  const translation = translationForLocale(locale);
  const [verse, setVerse] = useState<Verse | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = `${CACHE_PREFIX}${translation}`;

    const resolve = (value: Verse) => {
      if (active) setVerse(value);
    };

    const cached = readCache(cacheKey);
    if (cached) {
      const id = setTimeout(() => resolve(cached), 0);
      return () => {
        active = false;
        clearTimeout(id);
      };
    }

    const reference = pickRandomReference();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    fetchVerse(reference, translation, controller.signal)
      .then((result) => {
        writeCache(cacheKey, result);
        resolve(result);
      })
      .catch(() => resolve(fallbackFor(translation)))
      .finally(() => clearTimeout(timeoutId));

    return () => {
      active = false;
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [translation]);

  return (
    <blockquote
      className={cn(
        "space-y-1 rounded-lg bg-black/25 px-3 py-2 text-right backdrop-blur-sm",
        className,
      )}
    >
      <p className="min-h-[2.5rem] text-xs font-medium leading-snug text-foreground sm:text-sm lg:text-base">
        {verse ? (
          <span className="transition-opacity duration-500">“{verse.text}”</span>
        ) : (
          <span className="inline-flex flex-col gap-1" aria-hidden="true">
            <span className="block h-3 w-44 animate-pulse rounded-sm bg-foreground/20 sm:h-3.5 sm:w-56" />
            <span className="block h-3 w-32 animate-pulse rounded-sm bg-foreground/20 sm:h-3.5 sm:w-40" />
          </span>
        )}
      </p>
      <cite className="block text-[10px] font-light leading-none text-foreground/75 not-italic sm:text-xs">
        {verse ? `— ${verse.reference}` : "\u00A0"}
      </cite>
    </blockquote>
  );
}
