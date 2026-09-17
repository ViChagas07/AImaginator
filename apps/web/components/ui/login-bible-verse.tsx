"use client";

import { useEffect, useState } from "react";
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
  {
    reference: "Provérbios 3:5",
    text: "Confia no Senhor de todo o teu coração, e não te estribes no teu próprio entendimento.",
  },
  {
    reference: "Josué 1:9",
    text: "Esforça-te, e tem bom ânimo; não temas, nem te espantes, porque o Senhor teu Deus é contigo, por onde quer que andares.",
  },
  {
    reference: "Jeremias 29:11",
    text: "Porque eu bem sei os pensamentos que penso de vós, diz o Senhor; pensamentos de paz, e não de mal.",
  },
  {
    reference: "Salmos 46:1",
    text: "Deus é o nosso refúgio e fortaleza, socorro bem presente na angústia.",
  },
  {
    reference: "Isaías 41:10",
    text: "Não temas, porque eu sou contigo; não te assombres, porque eu sou o teu Deus; eu te fortaleço, e te ajudo, e te sustento com a destra da minha justiça.",
  },
];

export function LoginBibleVerse({ className }: { className?: string }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setIndex(Math.floor(Math.random() * VERSES.length));
    }, 0);
    return () => clearTimeout(timeoutId);
  }, []);

  const verse = VERSES[index];

  return (
    <p className={cn("text-center text-xs italic text-[#9CA3AF]", className)}>
      “{verse.text}” — {verse.reference}
    </p>
  );
}
