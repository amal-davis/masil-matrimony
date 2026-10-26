"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

/** Asks the server for the page again (e.g. after the stories couldn't be loaded). */
export function RetryButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      type="button"
      onClick={() => startTransition(() => router.refresh())}
      disabled={pending}
      className="mt-6 inline-flex h-12 items-center justify-center rounded-md border border-wine-600 px-6 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-wine-600 hover:text-white focus-visible:outline-wine-600 disabled:opacity-60"
    >
      {pending ? "Trying again…" : "Try again"}
    </button>
  );
}
