import type { Metadata } from "next";
import Link from "next/link";

import { SparkIcon } from "@/features/dashboard/components/icons";
import { MemberGrid } from "@/features/dashboard/components/member-grid";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import {
  EmptyState,
  LinkTabs,
  Notice,
  PageHeader,
  pageParam,
  Pagination,
  primaryButton,
  secondaryButton,
} from "@/features/dashboard/components/ui";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getMatches } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Find Matches" };

const PREFERENCES_PATH = "/dashboard/my-profile#preferences";
const BASE_PATH = "/dashboard/matches";

/**
 * The member's matches from their saved partner preferences, scored and
 * ranked by the API (backend/apps/profiles/matching.py). Nothing here invents,
 * pads or reorders results: an empty answer is shown as empty.
 */
export default async function MatchesPage({ searchParams }: PageProps<"/dashboard/matches">) {
  // The static preview (GitHub Pages) has no query string on the server; its sample data fits on one page.
  const query = STATIC_EXPORT ? {} : await searchParams;
  const page = pageParam(query.page);
  const mutual = query.mutual === "1";
  const data = await getMatches(page, mutual);

  const header = (
    <PageHeader
      title="Find Matches"
      description="Approved profiles that meet your must-haves, best fit with your partner preferences first."
      actions={
        <Link href={PREFERENCES_PATH} className={secondaryButton}>
          Edit my preferences
        </Link>
      }
    />
  );

  if (!data) {
    return (
      <>
        {header}
        <NoProfile>Matches are suggested from the partner preferences in your profile.</NoProfile>
      </>
    );
  }

  return (
    <>
      {header}

      {!data.preferences_set && (
        <Notice className="mb-5">
          You haven&apos;t set any partner preferences yet, so these are simply the newest approved profiles.{" "}
          <Link href={PREFERENCES_PATH} className="font-medium text-wine-600 underline underline-offset-4">
            Add your preferences
          </Link>{" "}
          to see the profiles that suit you best, with a match score.
        </Notice>
      )}

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <LinkTabs
          label="Which matches to show"
          tabs={[
            { href: BASE_PATH, label: "All matches", active: !mutual },
            { href: `${BASE_PATH}?mutual=1`, label: "Mutual matches", active: mutual },
          ]}
        />
        <p className="text-sm text-ink-muted" aria-live="polite">
          {data.count} {data.count === 1 ? "profile" : "profiles"}
        </p>
      </div>

      {data.results.length === 0 ? (
        page > 1 && data.count === 0 ? (
          <EmptyState
            icon={<SparkIcon className="size-6" />}
            title="No more matches"
            action={<Link href={mutual ? `${BASE_PATH}?mutual=1` : BASE_PATH} className={primaryButton}>Back to the first page</Link>}
          >
            You&apos;ve reached the end of the list.
          </EmptyState>
        ) : mutual ? (
          <EmptyState
            icon={<SparkIcon className="size-6" />}
            title="No mutual matches yet"
            action={<Link href={BASE_PATH} className={primaryButton}>See all matches</Link>}
          >
            None of your matches has must-haves that you also meet right now. Your other matches may still be a good fit.
          </EmptyState>
        ) : (
          <EmptyState
            icon={<SparkIcon className="size-6" />}
            title="No matches right now"
            action={<Link href={PREFERENCES_PATH} className={primaryButton}>Review my preferences</Link>}
          >
            No approved profile meets all of your must-haves at the moment. New members join every week. To see more
            profiles, you could mark fewer preferences as must-haves: the others still rank your matches.
          </EmptyState>
        )
      ) : (
        <>
          <MemberGrid members={data.results} />
          <Pagination page={page} count={data.count} basePath={BASE_PATH} params={{ mutual: mutual ? "1" : undefined }} />
          <p className="mt-6 text-sm leading-relaxed text-pretty text-ink-muted">
            The match score shows how many of your partner preferences a profile meets. It&apos;s a guide to help you
            choose, not a prediction of compatibility. A profile that hasn&apos;t stated a detail doesn&apos;t score for
            it. &ldquo;Mutual&rdquo; means you also meet every must-have that member has set.
          </p>
        </>
      )}
    </>
  );
}
