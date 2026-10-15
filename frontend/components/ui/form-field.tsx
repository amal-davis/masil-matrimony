import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Shared look for text inputs and selects on light surfaces. */
const controlBase =
  "h-12 w-full min-w-0 rounded-md border border-field-line bg-white text-base text-ink transition-colors placeholder:text-ink-muted/70 focus:border-wine-600 focus:outline-2 focus:-outline-offset-1 focus:outline-wine-600 disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-muted disabled:text-ink-muted aria-invalid:border-danger";

export const controlClasses = `${controlBase} px-3.5`;

/** Accessible attributes linking a control to its error message. */
export function errorProps(id: string, message?: string) {
  return message ? { "aria-invalid": true as const, "aria-describedby": `${id}-error` } : {};
}

/** Label above a control, with an optional hint and error message below it. */
export function Field({
  id,
  label,
  error,
  hint,
  className,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && !error && <p className="mt-1.5 text-sm text-ink-muted">{hint}</p>}
      <ErrorText id={`${id}-error`} message={error} />
    </div>
  );
}

export function ErrorText({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 flex items-start gap-1.5 text-sm text-danger">
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-4 shrink-0">
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.5a.75.75 0 0 0-1.5 0v4a.75.75 0 0 0 1.5 0v-4ZM10 14.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
          clipRule="evenodd"
        />
      </svg>
      {message}
    </p>
  );
}

/** Native select styled like the other controls, with a chevron. `compact` trims the padding for tight rows. */
export function Select({
  className,
  compact,
  children,
  ...props
}: ComponentProps<"select"> & { compact?: boolean }) {
  return (
    <div className="relative min-w-0">
      <select
        className={cn(
          controlBase,
          "appearance-none truncate",
          compact ? "pr-7 pl-2.5" : "pr-10 pl-3.5",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="currentColor"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-ink-muted",
          compact ? "right-2 size-4" : "right-3 size-5",
        )}
      >
        <path
          fillRule="evenodd"
          d="M5.22 7.72a.75.75 0 0 1 1.06 0L10 11.44l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.78a.75.75 0 0 1 0-1.06Z"
          clipRule="evenodd"
        />
      </svg>
    </div>
  );
}

/** One option of a segmented radio group (a row of equal buttons). */
export function SegmentedOption({
  label,
  invalid,
  ...props
}: Omit<ComponentProps<"input">, "type" | "className"> & { label: string; invalid?: boolean }) {
  return (
    <label className="relative min-w-0">
      <input type="radio" className="peer sr-only" {...props} />
      <span
        className={cn(
          "flex h-12 cursor-pointer items-center justify-center rounded-md border border-field-line px-2 text-base font-medium text-ink transition-colors",
          "peer-checked:border-wine-600 peer-checked:bg-wine-600 peer-checked:text-white",
          "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-wine-600",
          "hover:border-wine-600",
          invalid && "border-danger",
        )}
      >
        {label}
      </span>
    </label>
  );
}
