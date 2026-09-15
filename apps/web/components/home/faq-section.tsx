import {getTranslations} from "next-intl/server";

const FAQ_COUNT = 4;

export async function FaqSection() {
  const t = await getTranslations("landing");

  const faqs = Array.from({length: FAQ_COUNT}, (_, i) => ({
    question: t(`faq.${i}.question`),
    answer: t(`faq.${i}.answer`),
  }));

  return (
    <section
      aria-labelledby="faq-heading"
      className="mx-auto max-w-6xl px-4 py-16 sm:px-6"
    >
      <h2
        id="faq-heading"
        className="mb-8 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
      >
        {t("faqTitle")}
      </h2>
      <div className="max-w-3xl space-y-4">
        {faqs.map((faq) => (
          <details
            key={faq.question}
            className="rounded-lg border border-foreground/10 bg-surface px-5 py-4"
          >
            <summary className="cursor-pointer text-base font-medium text-foreground">
              {faq.question}
            </summary>
            <p className="mt-3 text-sm text-muted">{faq.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
