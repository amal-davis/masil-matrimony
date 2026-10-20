import { Container } from "@/components/ui/container";

/**
 * Mission and vision side by side: a white card and a wine card, so the pair reads
 * as two halves of one statement rather than two identical tiles.
 * Both are aspirations, not claims about what the service has achieved.
 */
export function MissionVision() {
  return (
    <section aria-label="Our mission and vision" className="bg-mist py-14 sm:py-20">
      <Container className="grid gap-5 md:grid-cols-2 md:gap-6">
        <article
          aria-labelledby="mission-title"
          className="flex flex-col rounded-xl border border-line bg-white p-6 sm:p-10"
        >
          <span aria-hidden="true" className="block h-px w-10 bg-wine-600" />
          <h2 id="mission-title" className="mt-5 text-2xl font-semibold sm:text-3xl">
            Our Mission
          </h2>
          <p className="mt-4 text-base leading-[1.75] text-pretty text-ink-muted sm:text-lg">
            Our mission is to create a thoughtful matrimonial experience that helps individuals and families explore
            compatible connections with greater clarity and confidence.
          </p>
        </article>

        <article
          aria-labelledby="vision-title"
          className="relative isolate flex flex-col overflow-hidden rounded-xl bg-wine-800 p-6 sm:p-10"
        >
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-10 bg-[radial-gradient(70%_90%_at_100%_0%,rgba(210,165,74,0.14),transparent_70%)]"
          />
          <span aria-hidden="true" className="block h-px w-10 bg-gold" />
          <h2 id="vision-title" className="mt-5 text-2xl font-semibold text-ivory sm:text-3xl">
            Our Vision
          </h2>
          <p className="mt-4 text-base leading-[1.75] text-pretty text-ivory/85 sm:text-lg">
            Our vision is to become a trusted destination for meaningful matchmaking, where individuals and families
            can approach the search for a life partner with care, respect, and a shared sense of purpose.
          </p>
        </article>
      </Container>
    </section>
  );
}
