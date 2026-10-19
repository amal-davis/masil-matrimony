import { Container } from "@/components/ui/container";
import { cn } from "@/lib/utils";

import { getSuccessStories } from "../api";
import type { SuccessStoriesResult } from "../types";
import { TestimonialSlider } from "./testimonial-slider";

/**
 * Homepage "Success Stories" section. Renders nothing when there are no
 * stories or loading fails, so a content outage never breaks the homepage.
 */
export async function SuccessStories() {
  let result: SuccessStoriesResult;
  try {
    result = await getSuccessStories();
  } catch (error) {
    console.error("Failed to load success stories", error);
    return null;
  }
  const { stories, source } = result;
  if (stories.length === 0) return null;

  return (
    <section id="success-stories" aria-labelledby="success-stories-title" className="scroll-mt-20 bg-mist py-14 sm:py-20">
      <Container size="wide">
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="success-stories-title" className="text-3xl font-semibold sm:text-4xl">
            Success Stories
          </h2>
          <p className="mt-3 text-lg text-pretty text-ink-muted">
            Every successful match begins a beautiful new chapter. Discover the stories of couples who
            found their life partners.
          </p>
          {source === "demo" && (
            <p className="mt-4 inline-flex rounded-full border border-accent-400 bg-accent-100 px-3 py-1 text-sm text-ink">
              Sample stories for preview. Real couples&apos; stories will appear here with their consent.
            </p>
          )}
        </div>

        <div className="mt-10">
          <TestimonialSlider stories={stories} label="Success stories" />
        </div>
      </Container>
    </section>
  );
}

/** Loading placeholder with roughly the loaded footprint. */
export function SuccessStoriesSkeleton() {
  return (
    <div aria-hidden="true" className="bg-mist py-14 sm:py-20">
      <Container size="wide">
        <div className="mx-auto h-24 max-w-md rounded-lg bg-white/70" />
        <div className="mt-10 grid gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 lg:gap-8">
          {Array.from({ length: 3 }, (_, i) => (
            <div
              key={i}
              className={cn(
                "h-[26rem] rounded-xl bg-white/70",
                i === 1 && "hidden sm:block",
                i === 2 && "hidden lg:block",
              )}
            />
          ))}
        </div>
      </Container>
    </div>
  );
}
