"use client";

import { useState, useTransition } from "react";

import { cn } from "@/lib/utils";

import { addToShortlist, removeFromShortlist } from "../actions";
import { BookmarkIcon } from "./icons";

/** Adds or removes a profile from the shortlist. The label changes only after the API confirms. */
export function ShortlistButton({
  profileCode,
  name,
  shortlisted,
  className,
}: {
  profileCode: string;
  name: string;
  shortlisted: boolean;
  className?: string;
}) {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");

  const toggle = () =>
    start(async () => {
      setError("");
      const result = shortlisted ? await removeFromShortlist(profileCode) : await addToShortlist(profileCode);
      if (!result.ok) setError(result.message);
    });

  return (
    <div className={cn("min-w-0", className)}>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={shortlisted}
        aria-label={`${shortlisted ? "Remove" : "Add"} ${name} ${shortlisted ? "from" : "to"} your shortlist`}
        className={cn(
          "inline-flex min-h-10 w-full items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:outline-wine-600 disabled:opacity-60",
          shortlisted ? "bg-brand-50 text-wine-600 hover:bg-brand-100" : "text-ink-muted hover:bg-mist hover:text-ink",
        )}
      >
        <BookmarkIcon className={cn("size-4.5", shortlisted && "fill-current")} />
        {busy ? "Saving…" : shortlisted ? "Shortlisted" : "Shortlist"}
      </button>
      <p role="alert" className="px-1 pt-1 text-center text-xs text-danger empty:hidden">
        {error}
      </p>
    </div>
  );
}
