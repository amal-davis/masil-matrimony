"use client";

import { useState, type ComponentProps } from "react";

import { controlClasses } from "@/components/ui/form-field";
import { EyeIcon, EyeOffIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/** Small building blocks shared by the sign-in, forgot-password and reset-password forms. */

export type Notice = { kind: "error" | "info"; message: string } | null;

export const primaryButton =
  "inline-flex h-13 w-full items-center justify-center gap-2.5 rounded-md bg-wine-600 px-8 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:opacity-60";

export const textLink =
  "inline-flex min-h-12 items-center rounded-sm px-1 text-[0.9375rem] font-medium text-wine-600 underline-offset-4 transition-colors hover:text-wine-800 hover:underline focus-visible:outline-wine-600";

/** Text field at the design's 52px field height. */
export const authControl = cn(controlClasses, "h-13");

export function Spinner() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="size-5 motion-safe:animate-spin">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Error and confirmation messages, each in its own live region so screen readers announce them.
 * The regions stay mounted when empty; `emptyOffset` (minus the parent's gap) cancels that gap so
 * they take no space.
 */
export function NoticeBox({ notice, emptyOffset = "-mt-5" }: { notice: Notice; emptyOffset?: "-mt-3" | "-mt-5" | "-mt-6" }) {
  return (
    <div className={cn(!notice && emptyOffset)}>
      <div role="alert" aria-live="assertive">
        {notice?.kind === "error" && (
          <p className="flex items-start gap-2.5 rounded-md border border-danger/40 bg-danger/5 px-4 py-3 text-[0.9375rem] text-ink">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-danger">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.5a.75.75 0 0 0-1.5 0v4a.75.75 0 0 0 1.5 0v-4ZM10 14.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="min-w-0">{notice.message}</span>
          </p>
        )}
      </div>
      <div role="status" aria-live="polite">
        {notice?.kind === "info" && (
          <p className="flex items-start gap-2.5 rounded-md border border-success/40 bg-success/5 px-4 py-3 text-[0.9375rem] text-ink">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-success">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.86-9.81a.75.75 0 0 0-1.22-.88l-3.24 4.5-1.6-1.6a.75.75 0 1 0-1.06 1.06l2.22 2.22a.75.75 0 0 0 1.14-.09l3.76-5.21Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="min-w-0">{notice.message}</span>
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Password field with a show/hide toggle. The toggle is a real button with a
 * fixed label and aria-pressed, so screen readers hear "Show password, toggle button".
 */
export function PasswordInput({ className, ...props }: Omit<ComponentProps<"input">, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        className={cn(authControl, "pr-14", className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        aria-label="Show password"
        aria-pressed={visible}
        aria-controls={props.id}
        disabled={props.disabled}
        className="absolute inset-y-0 right-0 flex w-13 items-center justify-center rounded-r-md text-ink-muted transition-colors hover:text-wine-600 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-wine-600 disabled:cursor-not-allowed"
      >
        {visible ? <EyeOffIcon className="size-5" /> : <EyeIcon className="size-5" />}
      </button>
    </div>
  );
}
