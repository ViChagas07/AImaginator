import {defineRouting} from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "pt-BR", "es", "fr", "de", "it"],
  defaultLocale: "pt-BR",
});
