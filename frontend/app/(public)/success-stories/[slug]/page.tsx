import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense, type ReactNode } from "react";

import { Container } from "@/components/ui/container";
import { ChevronLeftIcon } from "@/components/ui/icons";
import { getPrerenderedStorySlugs, getSuccessStory } from "@/features/success-stories/api";
import { RetryButton } from "@/components/ui/retry-button";
import type { SuccessStoryDetail } from "@/features/success-stories/types";

/**
 * One published success story, inside the public layout (shared site header and
 * footer). Loaded from the API by its slug on every request, so an unpublished
 * story disappears at once. Drafts and unknown slugs show the not-found page.
 *
 * Cache Components needs at least one prerendered value; with no sample stories a
 * placeholder is prerendered, which simply shows the not-found state.
 */
export async function generateStaticParams() {
  const slugs = getPrerenderedStorySlugs();
  return slugs.length > 0 ? slugs.map((slug) => ({ slug })) : [{ slug: "__none__" }];
}

export async function generateMetadata({ params }: PageProps<"/success-stories/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  try {
    const found = await getSuccessStory(slug);
    if (found) {
      return { title: `${found.story.heading} | Success Stories`, description: found.story.summary };
    }
  } catch {
    // The page itself shows the error; the title just stays generic.
  }
  return { title: "Success Story" };
}

export default function SuccessStoryPage({ params }: PageProps<"/success-stories/[slug]">) {
  return (
    <Suspense fallback={<StoryLoading />}>
      <StoryContent params={params} />
    </Suspense>
  );
}

async function StoryContent({ params }: { params: PageProps<"/success-stories/[slug]">["params"] }) {
  const { slug } = await params;
  let found: Awaited<ReturnType<typeof getSuccessStory>>;
  try {
    found = await getSuccessStory(slug);
  } catch (error) {
    console.error("Failed to load success story", error);
    return (
      <StoryFrame>
        <div className="rounded-xl border border-line bg-white px-6 py-12 text-center">
          <p className="text-lg text-ink-muted">We couldn&apos;t load this story just now. Please try again in a moment.</p>
          <RetryButton />
        </div>
      </StoryFrame>
    );
  }
  if (!found) notFound();
  return <StoryView story={found.story} isSample={found.source === "demo"} />;
}

function BackLink() {
  return (
    <Link
      href="/success-stories"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-sm text-[0.9375rem] font-medium text-wine-600 underline-offset-4 hover:underline focus-visible:outline-wine-600"
    >
      <ChevronLeftIcon className="size-4" />
      Back to Success Stories
    </Link>
  );
}

function StoryFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-mist py-8 sm:py-12 lg:py-16">
      <Container className="max-w-3xl">
        <nav aria-label="Breadcrumb" className="mb-4">
          <BackLink />
        </nav>
        {children}
      </Container>
    </div>
  );
}

function StoryView({ story, isSample }: { story: SuccessStoryDetail; isSample: boolean }) {
  const remote = typeof story.photo?.src === "string" && /^https?:\/\//.test(story.photo.src);
  return (
    <StoryFrame>
      <article aria-labelledby="story-title" className="overflow-hidden rounded-xl border border-line bg-white">
        {story.photo && (
          <div className="relative aspect-[4/3] w-full bg-mist sm:aspect-[16/10]">
            <Image
              src={story.photo.src}
              alt={story.photo.alt}
              fill
              priority
              sizes="(min-width: 768px) 720px, 100vw"
              unoptimized={remote}
              style={{ objectPosition: story.photo.position }}
              className="object-cover"
            />
          </div>
        )}
        <div className="px-5 py-7 sm:px-10 sm:py-10">
          {isSample && (
            <p className="mb-5 w-fit rounded-full border border-accent-400 bg-accent-100 px-3 py-1 text-sm text-ink">
              Sample story for preview
            </p>
          )}
          <h1 id="story-title" className="text-[1.875rem] leading-tight font-semibold break-words sm:text-4xl">
            {story.heading}
          </h1>
          {story.couple && <p className="mt-2 text-lg font-medium text-wine-600">{story.couple}</p>}
          {/* Plain-text paragraphs from the API: rendered as text, never as HTML. */}
          <div className="mt-6 flex max-w-[65ch] flex-col gap-5 text-[1.0625rem] leading-[1.75] text-pretty break-words text-ink sm:text-lg">
            {story.paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        </div>
      </article>
      <div className="mt-8 flex justify-center">
        <BackLink />
      </div>
    </StoryFrame>
  );
}

function StoryLoading() {
  return (
    <div aria-hidden="true" className="bg-mist py-8 sm:py-12 lg:py-16">
      <Container className="max-w-3xl">
        <div className="h-6 w-48 rounded bg-white/70" />
        <div className="mt-4 aspect-[4/3] rounded-xl bg-white/70 sm:aspect-[16/10]" />
        <div className="mt-6 h-40 rounded-xl bg-white/70" />
      </Container>
    </div>
  );
}
