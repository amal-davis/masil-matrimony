"use client";

import { useState } from "react";

import { ChevronLeftIcon, ChevronRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import type { SuccessStory } from "../types";
import { useSnapPager } from "../use-snap-pager";
import { TestimonialCard } from "./testimonial-card";

/** Beyond this many pages, a "3 / 10" counter replaces the dots so the row fits a 320px phone. */
const MAX_DOTS = 7;

type ArrowProps = { direction: "prev" | "next"; disabled: boolean; onClick: () => void; className?: string };

function ArrowButton({ direction, disabled, onClick, className }: ArrowProps) {
  const Icon = direction === "prev" ? ChevronLeftIcon : ChevronRightIcon;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "prev" ? "Previous stories" : "Next stories"}
      className={cn(
        "size-12 shrink-0 items-center justify-center rounded-md border bg-white text-wine-600 transition-[color,border-color,opacity] duration-200 focus-visible:outline-wine-600",
        className,
      )}
    >
      <Icon className="size-6" />
    </button>
  );
}

/**
 * Paged slider of success story cards: three per view on desktop, two on
 * tablets and one on phones (set by the item widths below). Swipe, trackpad
 * and keyboard scrolling are native, the mouse can drag, and the side arrows
 * and dots page through the groups.
 *
 * Arrows sit beside the track from xl; on smaller screens, where that space is
 * needed for the card, they float over the edges of the photos instead.
 */
export function TestimonialSlider({ stories, label }: { stories: SuccessStory[]; label: string }) {
  const { trackRef, page, pageCount, pageStarts, perView, measured, goTo, dragging, dragHandlers } =
    useSnapPager<HTMLUListElement>(stories.length);
  // Announced only after arrow/dot presses, so scrolling doesn't chatter.
  const [announcement, setAnnouncement] = useState("");

  function navigate(target: number) {
    const clamped = Math.min(Math.max(target, 0), pageCount - 1);
    goTo(clamped);
    const first = pageStarts[clamped] + 1;
    const last = Math.min(pageStarts[clamped] + perView, stories.length);
    setAnnouncement(
      first === last
        ? `Story ${first} of ${stories.length}`
        : `Stories ${first} to ${last} of ${stories.length}`,
    );
  }

  const hasPages = pageCount > 1;
  const atStart = page === 0;
  const atEnd = page === pageCount - 1;
  const controlsVisible = measured ? "opacity-100" : "opacity-0";

  // Desktop arrows beside the track.
  const sideArrow = cn(
    "hidden border-line hover:border-field-line disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line xl:row-start-1 xl:inline-flex",
    controlsVisible,
  );
  // Phone/tablet arrows floating over the photos; hidden at the ends.
  const overlayArrow = cn(
    "pointer-events-auto absolute top-1/2 inline-flex -translate-y-1/2 border-white/70 shadow-[0_12px_32px_rgba(36,26,28,0.14)] disabled:invisible",
    measured ? "opacity-100" : "opacity-0",
  );

  return (
    <div
      aria-roledescription="carousel"
      aria-label={label}
      className="[--gap:1rem] sm:[--gap:1.5rem] lg:[--gap:1.5rem] xl:[--gap:2rem]"
    >
      <div className="xl:grid xl:grid-cols-[auto_minmax(0,1fr)_auto] xl:items-center xl:gap-6">
        {hasPages && (
          <ArrowButton
            direction="prev"
            disabled={atStart}
            onClick={() => navigate(page - 1)}
            className={cn(sideArrow, "xl:col-start-1")}
          />
        )}

        {/*
          Always the middle (1fr) column. The arrows only render when there is more than one page,
          so without an explicit column a short list (1–3 stories) would auto-place into the first,
          content-sized "auto" column and squeeze the cards into a narrow strip.
        */}
        <div className="relative min-w-0 xl:col-start-2 xl:row-start-1">
          <ul
            ref={trackRef}
            {...dragHandlers}
            // Focusable so keyboard users can scroll it; cards hold no other controls.
            tabIndex={0}
            aria-label={`${label}, scrollable list`}
            className={cn(
              "flex snap-x snap-mandatory gap-(--gap) overflow-x-auto overscroll-x-contain scroll-smooth rounded-xl [scrollbar-width:none] motion-reduce:scroll-auto [&::-webkit-scrollbar]:hidden",
              "focus-visible:outline-wine-600",
              hasPages && "cursor-grab",
              // Fewer stories than fit in one view: centre them instead of leaving a gap on the right.
              measured && !hasPages && "justify-center",
              dragging && "cursor-grabbing select-none",
            )}
          >
            {stories.map((story) => (
              <li
                key={story.id}
                className="min-w-0 shrink-0 basis-full snap-start sm:basis-[calc((100%-var(--gap))/2)] lg:basis-[calc((100%-2*var(--gap))/3)]"
              >
                <TestimonialCard story={story} />
              </li>
            ))}
          </ul>

          {hasPages && (
            // Same size as one card's photo, so the arrows centre on the photos.
            <div className="pointer-events-none absolute inset-x-0 top-0 xl:hidden">
              <div className="aspect-[4/3] w-full sm:w-[calc((100%-var(--gap))/2)] lg:w-[calc((100%-2*var(--gap))/3)]" />
              <ArrowButton
                direction="prev"
                disabled={atStart}
                onClick={() => navigate(page - 1)}
                className={cn(overlayArrow, "left-2 sm:left-3")}
              />
              <ArrowButton
                direction="next"
                disabled={atEnd}
                onClick={() => navigate(page + 1)}
                className={cn(overlayArrow, "right-2 sm:right-3")}
              />
            </div>
          )}
        </div>

        {hasPages && (
          <ArrowButton
            direction="next"
            disabled={atEnd}
            onClick={() => navigate(page + 1)}
            className={cn(sideArrow, "xl:col-start-3")}
          />
        )}
      </div>

      {hasPages && (
        <div
          className={cn(
            "mt-6 flex items-center justify-center transition-opacity duration-200 sm:mt-8",
            controlsVisible,
          )}
        >
          {pageCount <= MAX_DOTS ? (
            pageStarts.map((start, i) => (
              <button
                key={start}
                type="button"
                onClick={() => navigate(i)}
                aria-label={`Go to page ${i + 1} of ${pageCount}`}
                aria-current={i === page ? "true" : undefined}
                className="group flex h-11 w-9 items-center justify-center rounded-full focus-visible:outline-wine-600 sm:size-12"
              >
                <span
                  className={cn(
                    "block h-2 rounded-full transition-all duration-200 motion-reduce:transition-none",
                    i === page ? "w-6 bg-wine-600" : "w-2 bg-field-line/50 group-hover:bg-field-line",
                  )}
                />
              </button>
            ))
          ) : (
            <p className="min-w-16 text-center font-medium text-ink tabular-nums">
              {page + 1} / {pageCount}
            </p>
          )}
        </div>
      )}

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
    </div>
  );
}
