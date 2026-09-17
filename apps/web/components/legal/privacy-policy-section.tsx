export type PrivacyPolicySectionProps = {
  title: string;
  body: string;
};

export function PrivacyPolicySection({title, body}: PrivacyPolicySectionProps) {
  return (
    <section className="border-b border-white/[0.08] py-10 first:pt-0 last:border-b-0 last:pb-0">
      <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-muted">{body}</p>
    </section>
  );
}
