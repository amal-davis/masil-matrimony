import Image from "next/image";

import { Container } from "@/components/ui/container";

import photo from "@/public/images/hero/kerala-wedding-family.jpg";

/** What can shape a good match. These are considerations, not platform features. */
const considerations = ["Personal values", "Lifestyle", "Aspirations", "Family expectations", "Mutual understanding"];

export function MatchmakingApproach() {
  return (
    <section aria-labelledby="approach-title" className="bg-mist py-14 sm:py-20">
      <Container className="grid items-center gap-10 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-16">
        <div>
          <h2 id="approach-title" className="text-3xl font-semibold sm:text-4xl">
            A More Thoughtful Approach to Matchmaking
          </h2>
          <span aria-hidden="true" className="mt-4 block h-px w-12 bg-wine-600" />
          <div className="mt-6 max-w-[62ch] space-y-5 text-base leading-[1.75] text-pretty text-ink-muted sm:text-lg">
            <p>
              We believe that finding a suitable life partner involves more than a quick search. Personal values,
              lifestyle, aspirations, family expectations, and mutual understanding can all play an important role.
            </p>
            <p>
              Massil Matrimony aims to provide a clear and accessible way to explore available profiles and learn
              about potential matches, while encouraging individuals and families to make decisions that feel right
              for them.
            </p>
          </div>

          <ul aria-label="What can shape a good match" className="mt-8 flex flex-wrap gap-x-6 gap-y-3">
            {considerations.map((item) => (
              <li key={item} className="flex items-center gap-2.5 text-[0.9375rem] font-medium text-wine-600">
                <span aria-hidden="true" className="size-1.5 shrink-0 rotate-45 bg-wine-600" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-white">
          <Image
            src={photo}
            alt="A bride and groom in Kerala wedding attire surrounded by their families"
            fill
            sizes="(min-width: 1024px) 30rem, 100vw"
            placeholder="blur"
            className="object-cover object-[center_25%]"
          />
        </div>
      </Container>
    </section>
  );
}
