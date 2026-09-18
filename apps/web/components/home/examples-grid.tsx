"use client";

import {useEffect, useRef, useState} from "react";
import {useTranslations} from "next-intl";
import Image from "next/image";

const EXAMPLE_IMAGES = [
  "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=800&q=60",
  "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?auto=format&fit=crop&w=800&q=60",
  "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=800&q=60",
  "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=800&q=60",
  "https://images.unsplash.com/photo-1490730141103-6cac27aaab94?auto=format&fit=crop&w=800&q=60",
  "/uma-borboleta-colorida-voando-pelo-ar-com-fundo-azul-vibrante-corpo-negro-e-asas-laranja-pretas-contra-um-pano-de-ia-rosa-387353274.webp",
  "/imagine.art-ai-2.jpg",
];

const SPANS = [
  "sm:col-span-2 sm:row-span-2",
  "",
  "",
  "sm:col-span-2",
  "",
  "",
  "col-span-2",
];

type ExampleItem = {
  prompt: string;
  imageAlt: string;
  src: string;
};

export function ExamplesGrid() {
  const t = useTranslations("landing");
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const items: ExampleItem[] = EXAMPLE_IMAGES.map((src, i) => ({
    src,
    prompt: t(`examples.${i}.prompt`),
    imageAlt: t(`examples.${i}.imageAlt`),
  }));

  useEffect(() => {
    if (openIndex === null) return;
    dialogRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenIndex(null);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [openIndex]);

  useEffect(() => {
    if (openIndex === null) return;
    const trigger = triggerRefs.current[openIndex];
    return () => {
      // devolver o foco de volta para o item que abriu o preview
      trigger?.focus();
    };
  }, [openIndex]);

  return (
    <section
      aria-labelledby="examples-heading"
      className="mx-auto max-w-6xl px-4 py-16 sm:px-6"
    >
      <h2
        id="examples-heading"
        className="mb-10 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
      >
        {t("examplesTitle")}
      </h2>
      <ul className="grid auto-rows-[180px] grid-cols-2 gap-4 sm:grid-cols-4">
        {items.map((item, i) => (
          <li key={item.src} className={SPANS[i] ?? ""}>
            <button
              ref={(el) => {
                triggerRefs.current[i] = el;
              }}
              type="button"
              onClick={() => setOpenIndex(i)}
              aria-haspopup="dialog"
              className="group relative block h-full w-full cursor-pointer overflow-hidden rounded-lg bg-surface"
            >
              <Image
                src={item.src}
                alt={item.imageAlt}
                fill
                sizes="(min-width: 640px) 50vw, 100vw"
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </button>
          </li>
        ))}
      </ul>

      {openIndex !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/80 p-4 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpenIndex(null);
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="example-preview-title"
            tabIndex={-1}
            className="w-full max-w-lg rounded-xl border border-foreground/10 bg-surface-raised p-6 shadow-2xl"
          >
            <div className="relative mb-4 aspect-[4/3] overflow-hidden rounded-lg bg-surface">
              <Image
                src={items[openIndex].src}
                alt={items[openIndex].imageAlt}
                fill
                sizes="(min-width: 640px) 512px, 100vw"
                className="object-cover"
              />
            </div>
            <h3
              id="example-preview-title"
              className="text-lg font-semibold tracking-tight text-foreground"
            >
              {t("previewDialogTitle")}
            </h3>
            <p className="mt-2 text-sm text-muted">{items[openIndex].prompt}</p>
            <button
              type="button"
              onClick={() => setOpenIndex(null)}
              className="mt-6 rounded-md bg-surface px-4 py-2 text-sm text-foreground"
            >
              {t("closePreview")}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
