"use client";

import { useId, useState } from "react";

import { CheckIcon, ChevronDownIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import type { Benefit } from "../packages";

type BenefitListProps = {
  benefits: Benefit[];
  /** Package name, for the toggle's accessible label. */
  packageName: string;
};

/**
 * Package benefits. Every benefit title is always listed.
 *
 * On phones the longer explanations are always shown: cards stack, so there is
 * nothing to balance. From `md`, where cards sit side by side, they
 * start collapsed behind a toggle so the cards stay a comparable height. Collapsed
 * explanations stay in the HTML (display: none), so the page reads the same without
 * JavaScript on phones and search engines still see the full text.
 */
export function BenefitList({ benefits, packageName }: BenefitListProps) {
  const listId = useId();
  const [expanded, setExpanded] = useState(false);
  const hasDetails = benefits.some((benefit) => benefit.detail);

  return (
    <div>
      <ul id={listId} className="flex flex-col gap-3.5">
        {benefits.map((benefit) => (
          <li key={benefit.title} className="flex gap-3">
            <CheckIcon className="mt-0.5 size-5 shrink-0 text-wine-600" />
            <div className="min-w-0">
              <p className={cn("text-base leading-snug text-pretty text-ink", benefit.detail && "font-medium")}>
                {benefit.title}
              </p>
              {benefit.detail && (
                <p
                  className={cn(
                    "mt-1 text-[0.9375rem] leading-relaxed text-pretty text-ink-muted",
                    !expanded && "md:hidden",
                  )}
                >
                  {benefit.detail}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>

      {hasDetails && (
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-label={`${expanded ? "Hide" : "Show"} benefit details for ${packageName}`}
          onClick={() => setExpanded((open) => !open)}
          className="mt-4 hidden min-h-11 items-center gap-1.5 rounded-sm text-[0.9375rem] font-medium text-wine-600 underline-offset-4 hover:underline focus-visible:outline-wine-600 md:inline-flex"
        >
          {expanded ? "Hide benefit details" : "Show benefit details"}
          <ChevronDownIcon
            className={cn(
              "size-4.5 transition-transform duration-200 motion-reduce:transition-none",
              expanded && "rotate-180",
            )}
          />
        </button>
      )}
    </div>
  );
}
