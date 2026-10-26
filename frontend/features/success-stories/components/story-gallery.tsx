import Link from "next/link";
import type { ReactNode } from "react";

import { Container } from "@/components/ui/container";
import { HeartIcon } from "@/components/ui/icons";

import { getSuccessStories } from "../api";
import type { SuccessStoriesResult } from "../types";
import { RetryButton } from "@/components/ui/retry-button";
import { TestimonialCard } from "./testimonial-card";

const pageLink =
  "inline-flex h-12 items-center justify-center rounded-md border border-wine-600 bg-white px-6 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-brand-50 focus-visible:outline-wine-600";

/**
 * Grid of published success stories, 20 per page: one column on phones, two
 * from sm and three from lg. Shows an empty state when there are none (e.g. on
 * the live site until real stories are published) and an error message with a
 * retry if loading fails. It never shows made-up stories instead.
 */
export async function StoryGallery({ page = 1 }: { page?: number }) {
  let result: SuccessStoriesResult;
  try {
    result = await getSuccessStories(page);
  } catch (error) {
    console.error("Failed to load success stories", error);
    return (
      <GalleryMessage action={<RetryButton />}>
        We couldn&apos;t load the success stories just now. Please try again in a moment.
      </GalleryMessage>
    );
  }

  const { stories, source } = result;
  if (stories.length === 0 && page > 1) {
    return (
      <GalleryMessage action={<Link href="/success-stories" className={`${pageLink} mt-6`}>Back to the first page</Link>}>
        There are no more stories here.
      </GalleryMessage>
    );
  }
  if (stories.length === 0) {
    return (
      <GalleryMessage>
        Our success-story gallery is growing. We look forward to sharing beautiful stories with you.
      </GalleryMessage>
    );
  }

  const sample = source === "demo";

  return (
    <section aria-labelledby="stories-title" className="bg-mist py-12 sm:py-16 lg:py-20">
      <Container>
        <h2 id="stories-title" className="sr-only">
          Couples&apos; stories
        </h2>

        {sample && (
          <p className="mx-auto mb-8 w-fit max-w-full rounded-2xl border border-accent-400 bg-accent-100 px-4 py-1.5 text-center text-sm text-ink sm:mb-10">
            Sample stories for preview. Real couples&apos; stories will appear here with their consent.
          </p>
        )}

        <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:gap-8">
          {stories.map((story) => (
            <li key={story.id} className="relative min-w-0">
              <TestimonialCard story={story} />
              {sample && (
                <span className="absolute top-3 left-3 rounded-full bg-wine-800/85 px-2.5 py-1 text-xs font-medium text-ivory">
                  Sample
                </span>
              )}
            </li>
          ))}
        </ul>

        {(result.hasPrevious || result.hasNext) && (
          <nav aria-label="More stories" className="mt-10 flex flex-wrap justify-center gap-3">
            {result.hasPrevious && (
              <Link href={page > 2 ? `/success-stories?page=${page - 1}` : "/success-stories"} className={pageLink}>
                Previous stories
              </Link>
            )}
            {result.hasNext && (
              <Link href={`/success-stories?page=${page + 1}`} className={pageLink}>
                More stories
              </Link>
            )}
          </nav>
        )}
      </Container>
    </section>
  );
}

/** Empty and error states: a quiet panel in place of the grid. */
function GalleryMessage({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <section aria-label="Success stories" className="bg-mist py-12 sm:py-16 lg:py-20">
      <Container>
        <div className="mx-auto flex max-w-xl flex-col items-center rounded-xl border border-line bg-white px-6 py-12 text-center sm:px-10">
          <span className="flex size-14 items-center justify-center rounded-full border border-accent-400 bg-accent-100 text-wine-600">
            <HeartIcon className="size-6" />
          </span>
          <p className="mt-5 text-lg leading-relaxed text-pretty text-ink-muted">{children}</p>
          {action}
        </div>
      </Container>
    </section>
  );
}

/** Loading placeholder with roughly the loaded footprint. */
export function StoryGallerySkeleton() {
  return (
    <div aria-hidden="true" className="bg-mist py-12 sm:py-16 lg:py-20">
      <Container>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:gap-8">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-[26rem] rounded-xl bg-white/70" />
          ))}
        </div>
      </Container>
    </div>
  );
}
