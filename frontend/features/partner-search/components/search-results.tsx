"use client";

import { useSearchParams } from "next/navigation";

import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";

import { describeFilters, filtersFromQuery } from "../schema";
import { PartnerSearchFilter } from "./partner-search-filter";

/**
 * The search form, prefilled from the URL, and a summary of the chosen filters.
 * The results themselves are SearchResultList, rendered by the page.
 *
 * Reads the query in the browser (useSearchParams) rather than from the page's
 * searchParams, so /search also works as a static page (the GitHub Pages
 * preview). Render it inside <Suspense>.
 */
export function SearchResults() {
  const params = useSearchParams();
  const query: Record<string, string[]> = {};
  params.forEach((value, key) => {
    (query[key] ??= []).push(value);
  });
  const filters = filtersFromQuery(query);
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
          {/* The static preview has no API; the live site lists the results below this summary. */}
          {STATIC_EXPORT && (
            <div role="status" className="mt-6 rounded-xl border border-accent-400 bg-accent-100 px-5 py-4 text-ink">
              <p className="font-semibold">This is a design preview.</p>
              <p className="mt-1 text-ink-muted">Search results appear on the live site for signed-in members.</p>
            </div>
          )}
        </section>
      )}
    </>
  );
}
