import Image from "next/image";

import { Container } from "@/components/ui/container";
import { ArrowRightIcon } from "@/components/ui/icons";

import monogram from "@/public/images/masil-matrimony-monogram.png";
import bannerPhoto from "@/public/images/hero/kerala-wedding-family.jpg";

import { brandBanner, brandFeatures } from "../content";

/**
 * Full-width brand banner: couple photo on the left, fading into the wine
 * background, with the brand heading, four feature cards, a short statement
 * and a call to action on the right.
 *
 * Below xl (1280px) the photo becomes a band across the top that fades
 * into the wine background, and the content stacks beneath it.
 */
export function BrandBanner() {
  return (
    <section aria-labelledby="brand-banner-title" className="relative isolate overflow-hidden bg-wine-900">
      <div className="absolute inset-x-0 top-0 -z-10 h-[21rem] min-[480px]:h-[26rem] md:h-[30rem] lg:h-[34rem] xl:right-auto xl:h-full xl:w-[66%]">
        <Image
          src={bannerPhoto}
          alt="A smiling bride and groom in Kerala wedding attire, with their families around them"
          fill
          sizes="(min-width: 1280px) 66vw, 100vw"
          placeholder="blur"
          className="object-cover object-[18%_30%] lg:object-[center_30%] xl:object-[left_32%]"
        />
        {/* Below xl: the photo band fades into the wine background below it. */}
        <div className="absolute inset-0 bg-gradient-to-b from-wine-900/10 via-wine-900/35 via-55% to-wine-900 xl:hidden" />
        {/* Desktop: the photo fills the left two thirds and dissolves into the wine behind the text. */}
        <div className="absolute inset-0 hidden bg-[linear-gradient(90deg,rgba(31,5,11,0.05)_0%,rgba(31,5,11,0.15)_45%,rgba(31,5,11,0.7)_75%,rgb(31,5,11)_100%)] xl:block" />
        <div className="absolute inset-0 hidden bg-gradient-to-t from-wine-900/60 via-transparent via-30% to-wine-900/40 xl:block" />
      </div>

      <Container
        size="wide"
        className="grid pt-[16rem] pb-14 min-[480px]:pt-[20rem] sm:pb-16 md:pt-[23rem] lg:pt-[27rem] xl:min-h-[44rem] xl:grid-cols-12 xl:items-center xl:py-24"
      >
        <div className="xl:col-span-7 xl:col-start-6">
          <div className="flex items-center gap-4 sm:gap-5">
            <Image
              src={monogram}
              alt=""
              sizes="80px"
              className="h-14 w-auto shrink-0 drop-shadow-[0_18px_28px_rgba(0,0,0,0.45)] sm:h-16 xl:h-[4.5rem]"
            />
            <h2
              id="brand-banner-title"
              className="text-[2.375rem] leading-[1.05] font-medium text-ivory sm:text-5xl xl:text-[3.5rem]"
            >
              {brandBanner.name}
            </h2>
          </div>
          <p className="mt-4 font-display text-2xl leading-snug text-gold-soft italic sm:text-[1.75rem]">
            {brandBanner.tagline}
          </p>

          <ul className="mt-8 grid grid-cols-1 gap-3 min-[400px]:grid-cols-2 sm:gap-4 lg:mt-10 lg:grid-cols-4">
            {brandFeatures.map(({ title, description, Icon }) => (
              <li
                key={title}
                className="flex gap-4 rounded-xl border border-gold/20 bg-white/[0.06] p-4 backdrop-blur-sm transition-colors duration-200 hover:border-gold/45 hover:bg-white/[0.09] min-[400px]:flex-col min-[400px]:gap-3 sm:p-5"
              >
                <span className="flex size-11 shrink-0 items-center justify-center rounded-full border border-gold/35 text-gold">
                  <Icon className="size-[1.375rem]" />
                </span>
                <div className="min-w-0">
                  <h3 className="font-sans text-base leading-snug font-medium text-ivory sm:text-[1.0625rem]">
                    {title}
                  </h3>
                  <p className="mt-1 text-base leading-relaxed text-ivory/75 xl:text-[0.9375rem]">{description}</p>
                </div>
              </li>
            ))}
          </ul>

          <p className="mt-8 max-w-[60ch] text-base leading-[1.7] text-pretty text-ivory/90 sm:text-lg lg:mt-10">
            {brandBanner.description}
          </p>

          <a
            href={brandBanner.cta.href}
            className="group mt-8 inline-flex h-13 w-full items-center justify-center gap-2.5 rounded-md bg-gold px-8 text-base font-medium text-wine-900 transition-colors duration-200 hover:bg-gold-soft focus-visible:outline-gold min-[400px]:w-auto"
          >
            {brandBanner.cta.label}
            <ArrowRightIcon className="size-5 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
          </a>
        </div>
      </Container>
    </section>
  );
}
