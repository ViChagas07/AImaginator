"use client";

import { cn } from "@/lib/utils";

type Verse = {
  reference: string;
  text: string;
};

const VERSES: Verse[] = [
  {
    reference: "João 3:16",
    text: "Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito, para que todo aquele que nele crê não pereça, mas tenha a vida eterna.",
  },
  {
    reference: "Salmos 23:1",
    text: "O Senhor é o meu pastor; nada me faltará.",
  },
  {
    reference: "Filipenses 4:13",
    text: "Posso todas as coisas naquele que me fortalece.",
  },
];

export function LoginBibleVerse({ className }: { className?: string }) {
  const verse = VERSES[0];
  return (
    <p className={cn("text-center text-xs italic text-[#9CA3AF]", className)}>
      “{verse.text}” — {verse.reference}
    </p>
  );
}
