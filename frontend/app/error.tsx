"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    // Replace with an error reporting service when one is chosen.
    console.error(error);
  }, [error]);

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-ink-muted">Please try again. If the problem continues, contact support.</p>
      <Button className="mt-8" onClick={() => retry()}>
        Try again
      </Button>
    </main>
  );
}
