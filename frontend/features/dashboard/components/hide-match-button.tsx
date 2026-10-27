"use client";

import { useState, useTransition } from "react";

import { cn } from "@/lib/utils";

import { hideMatch } from "../actions";

/** Removes a suggestion from the member's own matches. The other member isn't told. */
export function HideMatchButton({ profileCode, name, className }: { profileCode: string; name: string; className?: string }) {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");

  const hide = () =>
    start(async () => {
      setError("");
      const result = await hideMatch(profileCode);
      if (!result.ok) setError(result.message);
    });

  return (
    <div className={cn("min-w-0", className)}>
      <button
        type="button"
        onClick={hide}
        disabled={busy}
        aria-label={`Hide ${name} from your matches`}
        className="inline-flex min-h-10 w-full items-center justify-center rounded-lg px-2 text-sm font-medium text-ink-muted transition-colors hover:bg-mist focus-visible:outline-wine-600 disabled:opacity-60"
      >
        {busy ? "Hiding…" : "Hide"}
      </button>
      <p role="alert" className="px-2 text-xs text-danger empty:hidden">
        {error}
      </p>
    </div>
  );
}
