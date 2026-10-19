"use client";

import Image from "next/image";
import { useState } from "react";

import type { SuccessStory } from "../types";

// One card per view on phones, two from sm, three (up to ~430px in the wide container) from lg.
const photoSizes = "(min-width: 1024px) 440px, (min-width: 640px) 50vw, 100vw";

/** Success story card: couple photo, heading, then the couple's message. */
export function TestimonialCard({ story }: { story: SuccessStory }) {
  const [photoFailed, setPhotoFailed] = useState(false);
  const headingId = `${story.id}-heading`;

  return (
    <article
      aria-labelledby={headingId}
      className="flex h-full flex-col overflow-hidden rounded-xl border border-line bg-white transition-colors duration-200 hover:border-field-line/70"
    >
      <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden bg-mist">
        {story.photo && !photoFailed ? (
          <Image
            src={story.photo.src}
            alt={story.photo.alt}
            fill
            sizes={photoSizes}
            placeholder={typeof story.photo.src === "string" ? "empty" : "blur"}
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
        <h3 id={headingId} className="font-sans text-xl leading-snug font-medium text-ink">
          {story.heading}
        </h3>
        <p className="mt-3 text-base leading-[1.65] text-pretty text-ink-muted lg:text-[1.0625rem]">
          {story.message}
        </p>
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
