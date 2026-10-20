import Image from "next/image";
import Link from "next/link";

import { Container } from "@/components/ui/container";
import { ArrowRightIcon } from "@/components/ui/icons";
import { headerActions } from "@/lib/site";

import heroPhoto from "@/public/images/hero/garlanded-couple.jpg";

/**
 * Split hero for the About Us page: text on the wine band, a framed photo beside it
 * from lg and stacked beneath it on smaller screens.
 */
export function AboutHero() {
  return (
    <section aria-labelledby="about-title" className="relative isolate overflow-hidden bg-wine-800">
      {/* Soft glow behind the photo; decorative only. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(55%_70%_at_80%_45%,rgba(210,165,74,0.12),transparent_70%)]"
      />

      <Container className="grid items-center gap-10 py-12 sm:py-16 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-16 lg:py-20">
        <div className="animate-[hero-rise_700ms_cubic-bezier(0.2,0.7,0.2,1)_both] motion-reduce:animate-none">
          <p className="text-sm font-medium tracking-[0.12em] text-gold uppercase">Get to know Massil Matrimony</p>
          <h1
            id="about-title"
            className="mt-4 text-[2.25rem] leading-[1.1] font-medium text-ivory sm:text-5xl xl:text-[3.5rem]"
          >
            Bringing Hearts and Families Together
          </h1>
          <p className="mt-5 max-w-[56ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            At Massil Matrimony, we believe that finding a life partner is a meaningful journey shaped by shared
            values, mutual understanding, and the people who matter most.
          </p>

          <div className="mt-8 flex flex-col gap-3 min-[400px]:flex-row min-[400px]:flex-wrap min-[400px]:items-center sm:gap-4">
            <Link
              href={headerActions.search.href}
              className="group inline-flex h-13 items-center justify-center gap-2.5 rounded-md bg-gold px-8 text-base font-medium text-wine-900 transition-colors duration-200 hover:bg-gold-soft focus-visible:outline-gold"
            >
              Explore Profiles
              <ArrowRightIcon className="size-5 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
            </Link>
            <Link
              href="/#how-it-works"
              className="inline-flex h-13 items-center justify-center rounded-md border border-gold/80 px-7 text-base font-medium text-gold-soft transition-colors duration-200 hover:bg-gold hover:text-wine-900 focus-visible:outline-gold"
            >
              How It Works
            </Link>
          </div>
        </div>

        {/* The photo sits on an offset gold hairline frame. */}
        <div className="relative mx-auto w-full max-w-xl lg:max-w-none">
          <div aria-hidden="true" className="absolute inset-0 translate-x-3 translate-y-3 rounded-xl border border-gold/45 sm:translate-x-4 sm:translate-y-4" />
          <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-wine-900 lg:aspect-[4/5]">
            <Image
              src={heroPhoto}
              alt="A newly married couple in traditional wedding attire and rose garlands, smiling at each other"
              fill
              preload
              sizes="(min-width: 1024px) 40vw, (min-width: 640px) 576px, 100vw"
              placeholder="blur"
              className="object-cover object-[center_32%] lg:object-[52%_center]"
            />
          </div>
        </div>
      </Container>
    </section>
  );
}
