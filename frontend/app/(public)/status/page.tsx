import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { ApiStatus } from "@/features/system-status/components/api-status";

export const metadata: Metadata = {
  title: "System status",
  robots: { index: false, follow: false },
};

export default function StatusPage() {
  return (
    <Container className="max-w-2xl py-16">
      <h1 className="text-3xl font-semibold">System status</h1>
      <p className="mt-2 text-ink-muted">Live connectivity check between the website and the API.</p>
      <div className="mt-8">
        <Suspense fallback={<p className="text-sm text-ink-muted">Checking the API&hellip;</p>}>
          <ApiStatus />
        </Suspense>
      </div>
    </Container>
  );
}
