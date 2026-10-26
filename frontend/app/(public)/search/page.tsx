import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { SearchResultList, SearchResultListSkeleton } from "@/features/partner-search/components/search-result-list";
import { SearchResults } from "@/features/partner-search/components/search-results";

export const metadata: Metadata = {
  title: "Search your partner",
  description: "Search Maasil Matrimony profiles by age, height, religion, community and location.",
};

/** Reads the query and the session inside <Suspense>, so the heading and form above stay prerendered. */
async function Results({ searchParams }: { searchParams: PageProps<"/search">["searchParams"] }) {
  return <SearchResultList query={await searchParams} />;
}

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <Container className="py-10 sm:py-14">
      <h1 className="text-3xl font-semibold sm:text-4xl">Search your partner</h1>
      <p className="mt-2 text-lg text-ink-muted">Discover compatible profiles based on your preferences.</p>
      <Suspense fallback={<div className="mt-8 h-96 rounded-xl border border-line bg-white" />}>
        <SearchResults />
      </Suspense>
      {/* The static preview (GitHub Pages) has no API or session: it shows the form only. */}
      {!STATIC_EXPORT && (
        <Suspense fallback={<SearchResultListSkeleton />}>
          <Results searchParams={searchParams} />
        </Suspense>
      )}
    </Container>
  );
}
