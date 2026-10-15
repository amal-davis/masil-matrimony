"use client";

import Image from "next/image";
import {
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type FocusEvent,
  type PointerEvent,
  type ReactNode,
} from "react";

import { Container } from "@/components/ui/container";
import { cn } from "@/lib/utils";

import type { HeroSlide } from "../slides";

const reducedMotionQuery = "(prefers-reduced-motion: reduce)";

function subscribeToReducedMotion(callback: () => void) {
  const query = window.matchMedia(reducedMotionQuery);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

const pad = (value: number) => String(value).padStart(2, "0");

/** Horizontal distance (px) a drag must travel to change slide. */
const SWIPE_THRESHOLD = 60;
/** Movement (px) before deciding whether a gesture is a horizontal drag or a scroll. */
const DRAG_SLOP = 8;
/** Drags never start on these, so the form and indicators keep working normally. */
const NO_DRAG = "[data-no-drag], a, button, input, select, textarea, label";

type Drag = { pointerId: number; x: number; y: number; axis: "x" | "y" | null; dx: number };

type HeroSliderProps = {
  slides: HeroSlide[];
  /** Autoplay interval; the progress bar fills over the same time. */
  durationMs: number;
  /** Visually hidden page heading. */
  title: string;
  /** Content that stays put while slides change (the registration form). */
  aside: ReactNode;
};

/**
 * Full-width homepage hero: crossfading background images with per-slide copy on
 * the left and a fixed aside on the right (stacked below on smaller screens).
 *
 * Timing is driven by the active progress bar's CSS animation: when it ends the
 * slider advances, and pausing just pauses the animation. That keeps the bar and
 * the autoplay in sync with no timers to clean up.
 *
 * Slides change by autoplay, the pagination bars, or by dragging/swiping
 * horizontally anywhere on the hero outside the aside.
 */
export function HeroSlider({ slides, durationMs, title, aside }: HeroSliderProps) {
  const count = slides.length;
  const [index, setIndex] = useState(0);
  const [seen, setSeen] = useState<ReadonlySet<number>>(() => new Set([0]));
  const [hovered, setHovered] = useState(false);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<Drag | null>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const [asideActive, setAsideActive] = useState(false);
  const reducedMotion = useSyncExternalStore(
    subscribeToReducedMotion,
    () => window.matchMedia(reducedMotionQuery).matches,
    () => false,
  );

  const animated = count > 1 && !reducedMotion;
  const running = animated && !hovered && !dragging && !asideActive;
  const slide = slides[index];
  const nextIndex = (index + 1) % count;

  function goTo(target: number) {
    const next = (target + count) % count;
    setIndex(next);
    setSeen((previous) => (previous.has(next) ? previous : new Set(previous).add(next)));
  }

  function onAsideBlur(event: FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget)) setAsideActive(false);
  }

  /** Nudge the slide text along with the pointer; `null` resets it. */
  function followPointer(dx: number | null, animate = false) {
    const text = textRef.current;
    if (!text) return;
    text.style.transition = animate ? "transform 300ms cubic-bezier(0.25, 1, 0.5, 1), opacity 300ms" : "";
    text.style.transform = dx === null ? "" : `translateX(${dx * 0.35}px)`;
    text.style.opacity = dx === null ? "" : String(Math.max(0.4, 1 - Math.abs(dx) / 500));
  }

  function onPointerDown(event: PointerEvent<HTMLElement>) {
    if (count < 2 || !event.isPrimary || event.button !== 0) return;
    if ((event.target as Element).closest(NO_DRAG)) return;
    drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, axis: null, dx: 0 };
    // Stop the mouse from selecting text while dragging.
    if (event.pointerType === "mouse") event.preventDefault();
  }

  function onPointerMove(event: PointerEvent<HTMLElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const dx = event.clientX - current.x;
    const dy = event.clientY - current.y;

    if (current.axis === null) {
      if (Math.abs(dx) < DRAG_SLOP && Math.abs(dy) < DRAG_SLOP) return;
      current.axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
      if (current.axis === "y") {
        drag.current = null; // a vertical gesture: let the page scroll
        return;
      }
      event.currentTarget.setPointerCapture(event.pointerId);
      setDragging(true);
    }

    current.dx = dx;
    followPointer(dx);
  }

  function onPointerEnd(event: PointerEvent<HTMLElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    drag.current = null;
    if (current.axis !== "x") return;

    setDragging(false);
    if (event.type === "pointerup" && Math.abs(current.dx) >= SWIPE_THRESHOLD) {
      followPointer(null); // the incoming slide plays its own entrance
      goTo(index + (current.dx < 0 ? 1 : -1));
    } else {
      followPointer(null, true); // spring back
    }
  }

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Introduction"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd}
      onPointerCancel={onPointerEnd}
      className={cn(
        "relative isolate touch-pan-y touch-pinch-zoom overflow-hidden bg-wine-900",
        dragging && "cursor-grabbing select-none",
      )}
    >
      <h1 className="sr-only">{title}</h1>

      {/* Backgrounds: a top band on small screens, the full hero from lg. */}
      <div className="absolute inset-x-0 top-0 -z-10 h-[34rem] sm:h-[38rem] lg:h-full">
        {slides.map((item, i) =>
          // Only mount images that are showing, have shown, or come next, so the
          // first visit doesn't download every slide at once.
          i === index || i === nextIndex || seen.has(i) ? (
            <Image
              key={item.id}
              src={item.image}
              alt={i === index ? item.alt : ""}
              aria-hidden={i === index ? undefined : true}
              fill
              sizes="100vw"
              preload={i === 0}
              placeholder="blur"
              style={
                {
                  "--pos-mobile": item.position.mobile,
                  "--pos-desktop": item.position.desktop,
                } as CSSProperties
              }
              className={cn(
                "object-cover object-(--pos-mobile) transition-opacity duration-1000 ease-out motion-reduce:transition-none lg:object-(--pos-desktop)",
                i === index ? "opacity-100" : "opacity-0",
              )}
            />
          ) : null,
        )}
        {/* Readability overlays */}
        <div className="absolute inset-0 bg-gradient-to-b from-wine-900/75 via-wine-900/45 to-wine-900 lg:hidden" />
        <div className="absolute inset-0 hidden bg-gradient-to-r from-wine-900/90 via-wine-900/55 to-wine-900/25 lg:block" />
        <div className="absolute inset-x-0 bottom-0 hidden h-48 bg-gradient-to-t from-wine-900/85 to-transparent lg:block" />
      </div>

      <Container className="grid grid-cols-1 gap-8 pt-28 pb-12 sm:pt-32 lg:min-h-[46rem] lg:grid-cols-[minmax(0,7fr)_minmax(22rem,5fr)] lg:items-center lg:gap-12 lg:pt-28 lg:pb-16 xl:gap-20">
        <div
          className={cn(
            "flex min-h-[27rem] flex-col justify-end sm:min-h-[30rem] lg:min-h-0",
            count > 1 && !dragging && "cursor-grab",
          )}
          onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
          onPointerLeave={() => setHovered(false)}
        >
          {/* Announce slide changes only when the user drives them. */}
          <div ref={textRef} aria-live={running ? "off" : "polite"} aria-atomic="true">
            <div
              key={slide.id}
              role="group"
              aria-roledescription="slide"
              aria-label={`${index + 1} of ${count}`}
              className="animate-[hero-rise_700ms_cubic-bezier(0.2,0.7,0.2,1)_both] [text-shadow:0_1px_14px_rgba(31,5,11,0.55)] motion-reduce:animate-none"
            >
              {slide.eyebrow && (
                <p className="flex items-center gap-3 text-sm font-medium text-gold-soft sm:text-[0.9375rem]">
                  <span aria-hidden="true" className="h-px w-8 bg-gold" />
                  {slide.eyebrow}
                </p>
              )}
              <h2 className="mt-4 max-w-2xl text-[2.125rem] leading-[1.1] font-semibold text-ivory sm:text-5xl lg:text-[3.25rem] xl:text-6xl">
                {slide.heading}
              </h2>
              <p className="mt-4 max-w-xl text-base leading-relaxed text-ivory/90 sm:text-lg">
                {slide.description}
              </p>
            </div>
          </div>

          {count > 1 && (
            <div className="mt-8 flex items-center gap-2 sm:gap-3 lg:mt-12">
              <span className="w-6 font-display text-lg text-ivory tabular-nums" aria-hidden="true">
                {pad(index + 1)}
              </span>
              <div className="flex items-center">
                {slides.map((item, i) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => goTo(i)}
                    aria-label={`Go to slide ${i + 1}`}
                    aria-current={i === index ? "true" : undefined}
                    className="group flex h-11 w-12 items-center px-1 focus-visible:outline-gold sm:w-14"
                  >
                    <span className="relative h-0.5 w-full overflow-hidden rounded-full bg-ivory/30 transition-colors group-hover:bg-ivory/60">
                      {i === index && (
                        <span
                          key={index}
                          className="absolute inset-0 origin-left bg-gold"
                          style={
                            animated
                              ? {
                                  animation: `hero-progress ${durationMs}ms linear both`,
                                  animationPlayState: running ? "running" : "paused",
                                }
                              : undefined
                          }
                          onAnimationEnd={() => goTo(index + 1)}
                        />
                      )}
                    </span>
                  </button>
                ))}
              </div>
              <span className="font-display text-lg text-ivory/60 tabular-nums" aria-hidden="true">
                {pad(count)}
              </span>
            </div>
          )}
        </div>

        <div data-no-drag onFocus={() => setAsideActive(true)} onBlur={onAsideBlur}>
          {aside}
        </div>
      </Container>
    </section>
  );
}
