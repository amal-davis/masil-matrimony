import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { SearchResults } from "@/features/partner-search/components/search-results";

export const metadata: Metadata = {
  title: "Search your partner",
  description: "Search Maasil Matrimony profiles by age, height, religion, community and location.",
};

export default function SearchPage() {
  return (
    <Container className="py-10 sm:py-14">
      <h1 className="text-3xl font-semibold sm:text-4xl">Search your partner</h1>
      <p className="mt-2 text-lg text-ink-muted">Discover compatible profiles based on your preferences.</p>
      <Suspense fallback={<div className="mt-8 h-96 rounded-xl border border-line bg-white" />}>
        <SearchResults />
      </Suspense>
    </Container>
  );
}
