import type { Metadata } from "next";
import Link from "next/link";

import { SparkIcon } from "@/features/dashboard/components/icons";
import { MemberGrid } from "@/features/dashboard/components/member-grid";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { EmptyState, PageHeader, pageParam, Pagination, secondaryButton } from "@/features/dashboard/components/ui";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getMatches } from "@/features/dashboard/server-api";
import type { MemberCard } from "@/features/dashboard/types";

export const metadata: Metadata = { title: "Find Matches" };

export default async function MatchesPage({ searchParams }: PageProps<"/dashboard/matches">) {
  // The static preview (GitHub Pages) has no query string on the server; its sample data fits on one page.
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const data = await getMatches(page);

  return (
    <>
      <PageHeader
        title="Find Matches"
        description="Approved profiles that fit your partner preferences, newest first. Open a profile to send an interest."
        actions={
          <Link href="/dashboard/my-profile#preferences" className={secondaryButton}>
            Edit my preferences
          </Link>
        }
      />
      {!data ? (
        <NoProfile>Matches are suggested from the partner preferences in your profile.</NoProfile>
      ) : data.results.length === 0 ? (
        <EmptyState icon={<SparkIcon className="size-6" />} title="No matches yet">
          No approved profiles fit your partner preferences right now. New members join every week; you could also
          widen your preferences.
        </EmptyState>
      ) : (
        <>
          <p className="mb-4 text-sm text-ink-muted">{data.count} {data.count === 1 ? "profile" : "profiles"}</p>
          <MemberGrid members={data.results as (MemberCard & { shortlisted: boolean })[]} />
          <Pagination page={page} count={data.count} basePath="/dashboard/matches" />
        </>
      )}
    </>
  );
}
