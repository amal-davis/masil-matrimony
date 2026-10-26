import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { StoryGallery, StoryGallerySkeleton } from "@/features/success-stories/components/story-gallery";

export const metadata: Metadata = {
  title: "Success Stories",
  description:
    "Stories, photographs and celebrations that couples choose to share as they begin a new chapter together with Massil Matrimony.",
};

/** Reads ?page= inside Suspense, so the hero above stays part of the prerendered page. */
async function Gallery({ searchParams }: { searchParams: PageProps<"/success-stories">["searchParams"] }) {
  // The static preview (GitHub Pages) has no query string on the server; its samples fit on one page.
  const value = STATIC_EXPORT ? undefined : (await searchParams).page;
  const page = Number(Array.isArray(value) ? value[0] : value);
  return <StoryGallery page={Number.isInteger(page) && page > 0 ? page : 1} />;
}

export default function SuccessStoriesPage({ searchParams }: PageProps<"/success-stories">) {
  return (
    <>
      <section aria-labelledby="success-stories-title" className="relative isolate overflow-hidden bg-wine-800">
        {/* Soft glow behind the heading; decorative only. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[radial-gradient(60%_90%_at_50%_0%,rgba(210,165,74,0.14),transparent_70%)]"
        />

        <Container className="max-w-3xl py-12 text-center sm:py-16 lg:py-20">
          <p className="text-sm font-medium tracking-[0.12em] text-gold uppercase">Massil Matrimony</p>
          <h1
            id="success-stories-title"
            className="mt-4 text-[2.25rem] leading-[1.1] font-medium text-ivory sm:text-5xl xl:text-[3.5rem]"
          >
            Every Love Story Begins Somewhere
          </h1>
          <p className="mt-4 font-display text-xl text-gold-soft italic sm:text-2xl">
            Celebrating meaningful connections and beautiful beginnings.
          </p>
          <div aria-hidden="true" className="mx-auto mt-6 flex w-fit items-center gap-3">
            <span className="h-px w-10 bg-gold/60" />
            <span className="size-1.5 rotate-45 bg-gold" />
            <span className="h-px w-10 bg-gold/60" />
          </div>
          <p className="mx-auto mt-6 max-w-[58ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            Every meaningful relationship has its own story. Explore the moments, memories, and celebrations that
            couples choose to share as they begin a new chapter together.
          </p>
        </Container>
      </section>

      <Suspense fallback={<StoryGallerySkeleton />}>
        <Gallery searchParams={searchParams} />
      </Suspense>
    </>
  );
}
