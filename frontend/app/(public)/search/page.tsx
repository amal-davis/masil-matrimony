import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { PartnerSearchFilter } from "@/features/partner-search/components/partner-search-filter";
import { describeFilters, filtersFromQuery } from "@/features/partner-search/schema";

export const metadata: Metadata = {
  title: "Search your partner",
  description: "Search Maasil Matrimony profiles by age, height, religion, community and location.",
};

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <Container className="py-10 sm:py-14">
      <h1 className="text-3xl font-semibold sm:text-4xl">Search your partner</h1>
      <p className="mt-2 text-lg text-ink-muted">Discover compatible profiles based on your preferences.</p>
      <Suspense fallback={<div className="mt-8 h-96 rounded-xl border border-line bg-white" />}>
        <SearchContent searchParams={searchParams} />
      </Suspense>
    </Container>
  );
}

async function SearchContent({ searchParams }: Pick<PageProps<"/search">, "searchParams">) {
  const filters = filtersFromQuery(await searchParams);
  const summary = describeFilters(filters);

  return (
    <>
      {/* Keyed by the filters so the form resets when the URL changes. */}
      <PartnerSearchFilter key={JSON.stringify(filters)} initialValues={filters} className="mt-8" />

      {summary.length > 0 && (
        <section aria-labelledby="search-results-title" className="mt-10">
          <h2 id="search-results-title" className="text-2xl font-semibold">
            Your search
          </h2>
          <ul className="mt-3 flex flex-wrap gap-2" aria-label="Selected filters">
            {summary.map((item) => (
              <li key={item} className="rounded-full border border-line bg-white px-3 py-1 text-sm text-ink">
                {item}
              </li>
            ))}
          </ul>
          {/* No search API exists yet (planned: GET /profiles/search/). Never show sample profiles here. */}
          <div
            role="status"
            className="mt-6 rounded-xl border border-accent-400 bg-accent-100 px-5 py-4 text-ink"
          >
            <p className="font-semibold">Profile search isn&rsquo;t available yet.</p>
            <p className="mt-1 text-ink-muted">
              No profiles were searched. Your filters are saved in this page&rsquo;s address, so you can
              bookmark it and come back when search opens.
            </p>
          </div>
        </section>
      )}
    </>
  );
}
