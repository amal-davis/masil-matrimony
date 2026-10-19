"use client";

import { useId, useState } from "react";

import { cn } from "@/lib/utils";

import type { Faq } from "../faqs";

type FaqAccordionProps = {
  items: Faq[];
  /** Ids of questions open on first render. */
  defaultOpen?: string[];
  /** Heading level for each question, to fit the page outline. */
  headingLevel?: "h3" | "h2";
  className?: string;
};

/**
 * Accordion of questions and answers. Any number can be open at once.
 *
 * Each question is a real button inside a heading (WAI-ARIA accordion
 * pattern) with aria-expanded/aria-controls. Closed answers are `invisible`,
 * which removes them from the accessibility tree and tab order while still
 * letting the height animate; reduced motion makes it instant.
 */
export function FaqAccordion({ items, defaultOpen = [], headingLevel: Heading = "h3", className }: FaqAccordionProps) {
  const baseId = useId();
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set(defaultOpen));

  function toggle(id: string) {
    setOpen((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className={cn("border-t border-line", className)}>
      {items.map((item) => {
        const expanded = open.has(item.id);
        const buttonId = `${baseId}-${item.id}-question`;
        const panelId = `${baseId}-${item.id}-answer`;

        return (
          <div key={item.id} className="border-b border-line">
            <Heading className="font-sans text-base font-normal">
              <button
                type="button"
                id={buttonId}
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => toggle(item.id)}
                className={cn(
                  "group flex min-h-16 w-full items-center justify-between gap-4 py-4 text-left text-[1.0625rem] leading-snug font-medium transition-colors duration-200 focus-visible:outline-wine-600 sm:min-h-[4.5rem] sm:gap-6 sm:py-5 sm:text-lg",
                  expanded ? "text-wine-600" : "text-ink hover:text-wine-600",
                )}
              >
                <span className="min-w-0">{item.question}</span>
                <span
                  aria-hidden="true"
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-full border transition-colors duration-200",
                    expanded
                      ? "border-wine-600 bg-wine-600 text-white"
                      : "border-line text-wine-600 group-hover:border-wine-600",
                  )}
                >
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" className="size-4">
                    <path d="M4 10h12" />
                    {/* The vertical bar folds away: plus becomes minus. */}
                    <path
                      d="M10 4v12"
                      className={cn(
                        "origin-center transition-transform duration-200 motion-reduce:transition-none",
                        expanded && "scale-y-0",
                      )}
                    />
                  </svg>
                </span>
              </button>
            </Heading>

            <div
              id={panelId}
              role="region"
              aria-labelledby={buttonId}
              className={cn(
                "grid transition-[grid-template-rows,visibility] duration-250 ease-out motion-reduce:transition-none",
                expanded ? "visible grid-rows-[1fr]" : "invisible grid-rows-[0fr]",
              )}
            >
              <div className="overflow-hidden">
                <p className="max-w-[68ch] pb-5 text-base leading-[1.7] text-pretty text-ink-muted sm:pr-16 sm:pb-6">
                  {item.answer}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
