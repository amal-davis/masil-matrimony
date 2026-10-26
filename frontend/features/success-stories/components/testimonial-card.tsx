"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { ArrowRightIcon } from "@/components/ui/icons";

import type { SuccessStory } from "../types";

// One card per view on phones, two from sm, three (up to ~430px in the wide container) from lg.
const photoSizes = "(min-width: 1024px) 440px, (min-width: 640px) 50vw, 100vw";

/** A story's own page. */
export const storyPath = (slug: string) => `/success-stories/${encodeURIComponent(slug)}`;

/**
 * Success story card: couple photo, then the couple's names (or the heading when
 * no names were shared), the short description and "Read more". The whole card
 * opens the story: one link (the title) stretched over the card, so there is a
 * single focus stop and no nested interactive elements.
 */
export function TestimonialCard({ story }: { story: SuccessStory }) {
  const [photoFailed, setPhotoFailed] = useState(false);
  const headingId = `${story.id}-heading`;

  return (
    <article
      aria-labelledby={headingId}
      className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-line bg-white transition-colors duration-200 focus-within:border-wine-600 hover:border-field-line/70"
    >
      <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden bg-mist">
        {story.photo && !photoFailed ? (
          <Image
            src={story.photo.src}
            alt={story.photo.alt}
            fill
            sizes={photoSizes}
            placeholder={typeof story.photo.src === "string" ? "empty" : "blur"}
            // Story images come from the API, which already sizes and caches them.
            unoptimized={typeof story.photo.src === "string" && /^https?:\/\//.test(story.photo.src)}
            draggable={false}
            style={{ objectPosition: story.photo.position }}
            className="object-cover"
            onError={() => setPhotoFailed(true)}
          />
        ) : (
          <CouplePlaceholder />
        )}
      </div>

      <div className="flex flex-1 flex-col p-6 xl:p-8">
        <h3 id={headingId} className="font-sans text-xl leading-snug font-medium break-words text-ink">
          <Link
            href={storyPath(story.slug)}
            className="rounded-sm after:absolute after:inset-0 after:content-[''] focus-visible:outline-wine-600 group-hover:text-wine-600"
          >
            {story.couple ?? story.heading}
          </Link>
        </h3>
        {story.couple && <p className="mt-1 text-[0.9375rem] font-medium text-wine-600">{story.heading}</p>}
        <p className="mt-3 line-clamp-4 text-base leading-[1.65] text-pretty break-words text-ink-muted lg:text-[1.0625rem]">
          {story.summary}
        </p>
        {/* Part of the card's one link (above); hidden from screen readers so it isn't read twice. */}
        <span aria-hidden="true" className="mt-auto inline-flex items-center gap-1.5 pt-5 text-[0.9375rem] font-medium text-wine-600">
          Read more
          <ArrowRightIcon className="size-4 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
        </span>
      </div>
    </article>
  );
}

/** Neutral illustration used when a story has no (loadable) photo. */
function CouplePlaceholder() {
  return (
    <div className="absolute inset-0 flex items-end justify-center bg-gradient-to-b from-mist to-brand-100">
      <svg aria-hidden="true" viewBox="0 0 200 130" className="h-[78%] w-auto">
        <g className="text-brand-200" fill="currentColor">
          <circle cx="76" cy="44" r="21" />
          <path d="M28 130c2-30 21-50 48-50s46 20 48 50Z" />
        </g>
        <g className="text-brand-300" fill="currentColor">
          <circle cx="126" cy="48" r="19" />
          <path d="M82 130c2-27 19-45 44-45s42 18 44 45Z" />
        </g>
      </svg>
      <span className="sr-only">Photo coming soon</span>
    </div>
  );
}
