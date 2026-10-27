"use client";

import { useRef, type PointerEvent } from "react";

import { cn } from "@/lib/utils";

/** Half the thumb's width (`.range-input` in globals.css): a thumb's centre stops this far from either end. */
const THUMB_RADIUS = "0.875rem";

export type RangeValue = [low: number, high: number];

type RangeSliderProps = {
  id: string;
  label: string;
  min: number;
  max: number;
  step?: number;
  value: RangeValue;
  onChange: (value: RangeValue) => void;
  onBlur?: () => void;
  /** Accessible names of the two thumbs, e.g. ["Minimum age", "Maximum age"]. */
  thumbLabels: [string, string];
  /** What a screen reader announces for a thumb's value, e.g. "25 years". */
  valueText: (value: number, thumb: 0 | 1) => string;
  /** The selected range, shown beside the label. */
  display: string;
  invalid?: boolean;
  describedBy?: string;
  className?: string;
};

/**
 * A dual-thumb range slider: two native range inputs over one track, so both
 * thumbs keep the browser's keyboard, touch and screen-reader support. The low
 * thumb can't pass the high one (and vice versa); the thumbs may meet.
 */
export function RangeSlider({
  id,
  label,
  min,
  max,
  step = 1,
  value: [low, high],
  onChange,
  onBlur,
  thumbLabels,
  valueText,
  display,
  invalid,
  describedBy,
  className,
}: RangeSliderProps) {
  const track = useRef<HTMLDivElement>(null);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const span = max - min || 1;
  const offset = (value: number) => `calc(${THUMB_RADIUS} + (100% - 2 * ${THUMB_RADIUS}) * ${(value - min) / span})`;

  const setThumb = (thumb: 0 | 1, next: number) =>
    onChange(thumb === 0 ? [Math.min(next, high), high] : [low, Math.max(next, low)]);

  // Only the thumbs take pointer input (see globals.css), so a tap on the track lands here: move the nearer thumb.
  // A press on a thumb bubbles here too; leave it alone, or preventDefault would cancel the native drag.
  const onTrackPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.target instanceof HTMLInputElement) return;
    const rect = track.current?.getBoundingClientRect();
    if (!rect?.width || event.button !== 0) return;
    const fraction = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const next = Math.min(max, min + Math.round((fraction * span) / step) * step);
    const thumb = next <= low ? 0 : next >= high ? 1 : next - low <= high - next ? 0 : 1;
    event.preventDefault();
    setThumb(thumb, next);
    inputs.current[thumb]?.focus();
  };

  // Where the thumbs overlap, the one on top is the one that gets dragged. In the upper half of
  // the scale the low thumb has more room to move, so it goes on top; in the lower half, the high one.
  const lowOnTop = low > min + span / 2;

  return (
    <div role="group" aria-labelledby={`${id}-label`} aria-describedby={describedBy} className={className}>
      <div className="flex items-baseline justify-between gap-3">
        <span id={`${id}-label`} className="text-sm font-medium text-ink">
          {label}
        </span>
        <span className="text-sm font-semibold whitespace-nowrap text-wine-600 tabular-nums">{display}</span>
      </div>
      <div className="relative mt-1 h-10 md:mt-2 md:h-12" onPointerDown={onTrackPointerDown}>
        <div
          ref={track}
          className="absolute inset-x-3.5 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-field-line/30"
        />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-wine-600"
          style={{ left: offset(low), width: `calc((100% - 2 * ${THUMB_RADIUS}) * ${(high - low) / span})` }}
        />
        {([0, 1] as const).map((thumb) => {
          const value = thumb === 0 ? low : high;
          return (
            <input
              key={thumb}
              ref={(element) => {
                inputs.current[thumb] = element;
              }}
              id={`${id}-${thumb === 0 ? "min" : "max"}`}
              type="range"
              min={min}
              max={max}
              step={step}
              value={value}
              aria-label={thumbLabels[thumb]}
              aria-valuetext={valueText(value, thumb)}
              aria-invalid={invalid || undefined}
              onChange={(event) => setThumb(thumb, Number(event.target.value))}
              onBlur={onBlur}
              className={cn("range-input absolute inset-0 h-full w-full", (thumb === 0) === lowOnTop && "z-10")}
            />
          );
        })}
      </div>
    </div>
  );
}
