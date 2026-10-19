"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";

/**
 * First item of each page. The last page is pulled back so it is always full:
 * 7 items, 3 per view → pages start at 0, 3 and 4 (items 5–7).
 */
export function pageStarts(itemCount: number, perView: number): number[] {
  const pages = Math.max(1, Math.ceil(itemCount / perView));
  const lastStart = Math.max(0, itemCount - perView);
  return Array.from({ length: pages }, (_, page) => Math.min(page * perView, lastStart));
}

type PagerState = { perView: number; page: number; measured: boolean };

/** Mouse travel (px) before a press becomes a drag, and the drag distance that changes page. */
const DRAG_SLOP = 5;
const DRAG_THRESHOLD = 60;

type Drag = { pointerId: number; x: number; scrollLeft: number; page: number; active: boolean };

/**
 * Paging for a horizontal scroll-snap track. The CSS decides how many items fit
 * (so breakpoints live in one place); this hook measures that, splits the items
 * into pages, tracks the page in view, and scrolls to a page on request.
 * Native scrolling gives touch swiping, momentum and keyboard scrolling for free;
 * `dragHandlers` add click-and-drag paging for mouse users.
 */
export function useSnapPager<T extends HTMLElement>(itemCount: number) {
  const trackRef = useRef<T>(null);
  const [state, setState] = useState<PagerState>({ perView: 1, page: 0, measured: false });
  const [dragging, setDragging] = useState(false);
  const drag = useRef<Drag | null>(null);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    function update() {
      if (!track) return;
      const items = track.children as HTMLCollectionOf<HTMLElement>;
      const first = items[0];
      if (!first) return;

      const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
      const step = first.offsetWidth + gap;
      const perView = Math.max(1, Math.round((track.clientWidth + gap) / step));
      const starts = pageStarts(itemCount, perView);

      let page: number;
      if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 2) {
        page = starts.length - 1;
      } else {
        const firstVisible = Math.round(track.scrollLeft / step);
        page = starts.reduce(
          (best, start, i) =>
            Math.abs(start - firstVisible) < Math.abs(starts[best] - firstVisible) ? i : best,
          0,
        );
      }

      setState((prev) =>
        prev.perView === perView && prev.page === page && prev.measured
          ? prev
          : { perView, page, measured: true },
      );
    }

    update();
    const observer = new ResizeObserver(update);
    observer.observe(track);
    track.addEventListener("scroll", update, { passive: true });
    return () => {
      observer.disconnect();
      track.removeEventListener("scroll", update);
    };
  }, [itemCount]);

  const starts = pageStarts(itemCount, state.perView);

  function goTo(page: number) {
    const track = trackRef.current;
    const target = track?.children[starts[Math.min(Math.max(page, 0), starts.length - 1)]];
    if (!track || !(target instanceof HTMLElement)) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    track.scrollTo({
      left: target.offsetLeft - (track.children[0] as HTMLElement).offsetLeft,
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }

  function onPointerDown(event: PointerEvent<T>) {
    // Touch and pen already scroll natively; only the mouse needs help.
    if (event.pointerType !== "mouse" || event.button !== 0 || starts.length < 2) return;
    drag.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      scrollLeft: event.currentTarget.scrollLeft,
      page: state.page,
      active: false,
    };
    event.preventDefault(); // no text selection while dragging
  }

  function onPointerMove(event: PointerEvent<T>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const track = event.currentTarget;
    const dx = event.clientX - current.x;
    if (!current.active) {
      if (Math.abs(dx) < DRAG_SLOP) return;
      current.active = true;
      track.setPointerCapture(event.pointerId);
      // Snapping and smooth scrolling would fight the pointer while it moves.
      track.style.scrollSnapType = "none";
      track.style.scrollBehavior = "auto";
      setDragging(true);
    }
    track.scrollLeft = current.scrollLeft - dx;
  }

  function onPointerEnd(event: PointerEvent<T>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    drag.current = null;
    if (!current.active) return;

    const track = event.currentTarget;
    track.style.scrollSnapType = "";
    track.style.scrollBehavior = "";
    setDragging(false);

    const dx = event.clientX - current.x;
    const step = Math.abs(dx) >= DRAG_THRESHOLD && event.type === "pointerup" ? (dx < 0 ? 1 : -1) : 0;
    goTo(current.page + step);
  }

  return {
    trackRef,
    perView: state.perView,
    page: state.page,
    pageCount: starts.length,
    pageStarts: starts,
    /** False until the first client measurement; controls stay hidden until then. */
    measured: state.measured,
    goTo,
    /** True while the mouse is dragging the track. */
    dragging,
    /** Spread onto the track element. */
    dragHandlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp: onPointerEnd,
      onPointerCancel: onPointerEnd,
    },
  };
}
