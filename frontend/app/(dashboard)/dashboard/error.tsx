"use client";

import { primaryButton } from "@/features/dashboard/components/ui";

/** A dashboard page couldn't load its data (for example, the API is unreachable). */
export default function DashboardError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-danger/40 bg-white px-6 py-12 text-center">
      <h1 className="text-xl font-semibold">We couldn&apos;t load this page</h1>
      <p className="mx-auto mt-2 max-w-[48ch] text-[0.9375rem] text-ink-muted">
        This is usually temporary. Please check your connection and try again.
      </p>
      <button type="button" onClick={() => retry()} className={`${primaryButton} mt-6`}>
        Try again
      </button>
    </div>
  );
}
