import Link from "next/link";
import type { ReactNode } from "react";

import { LockIcon, SearchIcon, UserIcon } from "@/components/ui/icons";
import { RetryButton } from "@/components/ui/retry-button";
import { loginUrl } from "@/features/auth/constants";
import { MemberGrid } from "@/features/dashboard/components/member-grid";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { EmptyState, Notice, Pagination, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";

import { searchProfiles, type SearchOutcome } from "../api";
import { SEARCH_RESULTS_PATH } from "../schema";

/** The API's search parameters (backend/apps/profiles/search.py); anything else in the URL is ignored. */
export const SEARCH_PARAMS = [
  "gender",
  "age_min",
  "age_max",
  "height_min",
  "height_max",
  "religion",
  "caste",
  "location",
  "marital_status",
  "mother_tongue",
  "education",
  "occupation",
  "profile_id",
] as const;

/** Names for the advanced filters the API can refuse (backend/apps/profiles/search.py ADVANCED_FILTERS). */
const FILTER_LABELS: Record<string, string> = {
  marital_status: "marital status",
  mother_tongue: "mother tongue",
  education: "education",
  occupation: "occupation",
};

type Query = Record<string, string | string[] | undefined>;

export function searchQuery(query: Query, { withPage = true } = {}): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of [...SEARCH_PARAMS, ...(withPage ? ["page"] : [])]) {
    const raw = query[key];
    for (const value of Array.isArray(raw) ? raw : [raw]) {
      if (value?.trim()) params.append(key, value.trim());
    }
  }
  return params;
}

const PAGE_SIZE = 20;

/**
 * The profiles matching the search in the URL, from the real API. Shows exactly
 * what the API returns: no sample profiles, and an empty result stays empty.
 */
export async function SearchResultList({ query }: { query: Query }) {
  const params = searchQuery(query);
  const filters = searchQuery(query, { withPage: false });
  const here = `${SEARCH_RESULTS_PATH}${params.size ? `?${params}` : ""}`;
  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);

  let outcome: SearchOutcome;
  try {
    outcome = await searchProfiles(params);
  } catch (error) {
    console.error("Profile search failed", error);
    return (
      <Section>
        <EmptyState
          icon={<SearchIcon className="size-6" />}
          title="We couldn't search profiles just now"
          action={<RetryButton />}
        >
          Please check your connection and try again in a moment.
        </EmptyState>
      </Section>
    );
  }

  switch (outcome.kind) {
    case "signed_out":
      return (
        <Section>
          <EmptyState
            icon={<UserIcon className="size-6" />}
            title="Log in to see matching profiles"
            action={
              <Link href={loginUrl(here)} className={primaryButton}>
                Log in to search
              </Link>
            }
          >
            To protect our members&apos; privacy, profiles are visible only to registered members who are signed in.
            Your filters will be kept.
          </EmptyState>
        </Section>
      );
    case "no_profile":
      return (
        <Section>
          <NoProfile>Search shows other members once your own profile is created.</NoProfile>
        </Section>
      );
    case "invalid":
      return (
        <Section>
          <Notice tone="danger" role="alert">
            <p className="font-semibold">Please check your search.</p>
            <ul className="mt-1 list-disc pl-5">
              {Object.values(outcome.errors).map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          </Notice>
        </Section>
      );
    case "upgrade_required": {
      // Search again with only the basic filters the member's plan includes.
      const basic = new URLSearchParams(filters);
      for (const name of outcome.filters) basic.delete(name);
      return (
        <Section>
          <EmptyState
            icon={<LockIcon className="size-6" />}
            title="Advanced filters are part of paid memberships"
            action={
              <div className="flex flex-wrap justify-center gap-3">
                <Link href="/dashboard/membership" className={primaryButton}>
                  See membership plans
                </Link>
                <Link href={`${SEARCH_RESULTS_PATH}${basic.size ? `?${basic}` : ""}`} className={secondaryButton}>
                  Search without them
                </Link>
              </div>
            }
          >
            {outcome.message} You searched by {outcome.filters.map((name) => FILTER_LABELS[name] ?? name).join(", ")}.
          </EmptyState>
        </Section>
      );
    }
    case "past_end":
      return (
        <Section>
          <EmptyState
            title="There are no more results"
            action={
              <Link href={`${SEARCH_RESULTS_PATH}${filters.size ? `?${filters}` : ""}`} className={secondaryButton}>
                Back to the first page
              </Link>
            }
          />
        </Section>
      );
  }

  const { count, results } = outcome.page;
  return (
    <Section>
      <p role="status" className="mb-5 text-lg font-medium text-ink">
        {count === 0 ? "No profiles found" : `${count} ${count === 1 ? "profile" : "profiles"} found`}
      </p>
      {results.length === 0 ? (
        <EmptyState icon={<SearchIcon className="size-6" />} title="No profiles match your search">
          Try removing a filter or widening the age or height range. New profiles appear here as soon as they&apos;re
          approved.
        </EmptyState>
      ) : (
        <>
          <MemberGrid members={results} />
          <div className="mt-8">
            <Pagination
              page={page}
              count={count}
              pageSize={PAGE_SIZE}
              basePath={SEARCH_RESULTS_PATH}
              params={Object.fromEntries(filters)}
            />
          </div>
        </>
      )}
    </Section>
  );
}

function Section({ children }: { children: ReactNode }) {
  return (
    <section aria-labelledby="search-results-heading" className="mt-10">
      <h2 id="search-results-heading" className="sr-only">
        Search results
      </h2>
      {children}
    </section>
  );
}

/** Loading placeholder with roughly the loaded footprint. */
export function SearchResultListSkeleton() {
  return (
    <div aria-hidden="true" className="mt-10">
      <div className="mb-5 h-7 w-48 rounded bg-surface-muted" />
      <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-96 rounded-xl border border-line bg-white" />
        ))}
      </div>
    </div>
  );
}
