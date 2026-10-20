import Link from "next/link";

import { Container } from "@/components/ui/container";
import { ArrowRightIcon } from "@/components/ui/icons";
import { headerActions } from "@/lib/site";

/** Closing call to action: explore profiles, or get in touch. */
export function AboutCta() {
  return (
    <section aria-labelledby="about-cta-title" className="relative isolate overflow-hidden bg-wine-800">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(60%_90%_at_50%_0%,rgba(210,165,74,0.14),transparent_70%)]"
      />
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gold/40" />

      <Container className="max-w-3xl py-14 text-center sm:py-20">
        <h2 id="about-cta-title" className="text-3xl leading-[1.15] font-medium text-ivory sm:text-[2.75rem]">
          Your Journey Towards a Meaningful Connection Starts Here
        </h2>
        <p className="mx-auto mt-5 max-w-[56ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
          Discover Massil Matrimony and learn more about our approach to bringing individuals and families together.
        </p>

        <div className="mt-8 flex flex-col justify-center gap-3 min-[400px]:flex-row sm:gap-4">
          <Link
            href={headerActions.search.href}
            className="group inline-flex h-13 items-center justify-center gap-2.5 rounded-md bg-gold px-8 text-base font-medium text-wine-900 transition-colors duration-200 hover:bg-gold-soft focus-visible:outline-gold"
          >
            Explore Profiles
            <ArrowRightIcon className="size-5 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
          </Link>
          <Link
            href="/contact"
            className="inline-flex h-13 items-center justify-center rounded-md border border-gold/80 px-7 text-base font-medium text-gold-soft transition-colors duration-200 hover:bg-gold hover:text-wine-900 focus-visible:outline-gold"
          >
            Contact Us
          </Link>
        </div>

        <p className="mt-8 flex items-center justify-center gap-3 text-[0.9375rem] text-gold-soft">
          <span aria-hidden="true" className="h-px w-8 shrink-0 bg-gold" />
          Member registration opens soon.
          <span aria-hidden="true" className="h-px w-8 shrink-0 bg-gold" />
        </p>
      </Container>
    </section>
  );
}
