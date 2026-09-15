import {getTranslations} from "next-intl/server";
import Image from "next/image";

const STEP_IMAGES = [
  "https://images.unsplash.com/photo-1487958449943-2429e8be8625?auto=format&fit=crop&w=600&q=60",
  "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=600&q=60",
  "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=600&q=60",
];

export async function StepsSection() {
  const t = await getTranslations("landing");

  const steps = [0, 1, 2].map((i) => ({
    title: t(`steps.${i}.title`),
    description: t(`steps.${i}.description`),
    imageAlt: t(`steps.${i}.imageAlt`),
    src: STEP_IMAGES[i],
  }));

  return (
    <section aria-labelledby="steps-heading" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <h2
        id="steps-heading"
        className="mb-10 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
      >
        {t("stepsTitle")}
      </h2>
      <ol className="grid gap-8 sm:grid-cols-3">
        {steps.map((step, index) => (
          <li key={step.title} className="relative flex flex-col gap-4">
            <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-surface">
              <Image
                src={step.src}
                alt={step.imageAlt}
                fill
                sizes="(min-width: 640px) 33vw, 100vw"
                className="object-cover"
              />
            </div>
            <div className="flex items-baseline gap-3">
              <span
                aria-hidden
                className="text-sm font-medium text-muted"
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-foreground">
                  {step.title}
                </h3>
                <p className="mt-1 text-sm text-muted">{step.description}</p>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
