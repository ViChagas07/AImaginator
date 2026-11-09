import {getRequestConfig} from "next-intl/server";
import {hasLocale} from "next-intl";
import {routing} from "./routing";
import {pseudoEnabled, pseudoLocalize} from "./pseudo";

export default getRequestConfig(async ({requestLocale}) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale;
  const messages = (await import(`../messages/${locale}.json`)).default;

  return {
    locale,
    messages: pseudoEnabled() ? pseudoLocalize(messages) : messages,
  };
});
