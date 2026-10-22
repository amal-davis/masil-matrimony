import type { Metadata } from "next";
import Link from "next/link";

import { BookmarkIcon } from "@/features/dashboard/components/icons";
import { MemberGrid } from "@/features/dashboard/components/member-grid";
import { MemberSummary } from "@/features/dashboard/components/member-summary";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { ShortlistButton } from "@/features/dashboard/components/shortlist-button";
import { EmptyState, PageHeader, pageParam, Pagination, primaryButton } from "@/features/dashboard/components/ui";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getShortlist } from "@/features/dashboard/server-api";
import type { MemberCard } from "@/features/dashboard/types";

export const metadata: Metadata = { title: "Shortlisted Profiles" };

export default async function ShortlistedPage({ searchParams }: PageProps<"/dashboard/shortlisted">) {
  // The static preview (GitHub Pages) has no query string on the server; its sample data fits on one page.
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const data = await getShortlist(page);
  const available = data?.results.flatMap((entry) => (entry.profile.available ? [{ ...entry.profile, shortlisted: true }] : [])) ?? [];
  const unavailable = data?.results.filter((entry) => !entry.profile.available) ?? [];

  return (
    <>
      <PageHeader title="Shortlisted Profiles" description="Profiles you've saved to revisit and discuss with your family." />
      {!data ? (
        <NoProfile>Create your profile to start shortlisting members.</NoProfile>
      ) : data.results.length === 0 ? (
        <EmptyState
          icon={<BookmarkIcon className="size-6" />}
          title="Your shortlist is empty"
          action={
            <Link href="/dashboard/matches" className={primaryButton}>
              Browse matches
            </Link>
          }
        >
          Use “Shortlist” on a profile to keep it here.
        </EmptyState>
      ) : (
        <>
          {available.length > 0 && <MemberGrid members={available as (MemberCard & { shortlisted: boolean })[]} />}
          {unavailable.length > 0 && (
            <section aria-labelledby="unavailable-title" className="mt-8">
              <h2 id="unavailable-title" className="text-lg font-semibold">No longer available</h2>
              <ul className="mt-3 flex flex-col gap-3">
                {unavailable.map((entry) => (
                  <li key={entry.profile.profile_code} className="flex flex-col gap-3 rounded-xl border border-line bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
                    <MemberSummary member={entry.profile} />
                    <ShortlistButton profileCode={entry.profile.profile_code} name={entry.profile.display_name} shortlisted />
                  </li>
                ))}
              </ul>
            </section>
          )}
          <Pagination page={page} count={data.count} basePath="/dashboard/shortlisted" />
        </>
      )}
    </>
  );
}
