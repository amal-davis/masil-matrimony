import type { Metadata } from "next";
import Link from "next/link";

import { EyeIcon } from "@/features/dashboard/components/icons";
import { MemberSummary } from "@/features/dashboard/components/member-summary";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { EmptyState, PageHeader, pageParam, Pagination, primaryButton } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getProfileViewers } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Who Viewed My Profile" };

/**
 * Members who opened the member's profile, from the API. Without the feature
 * the API returns only how many did, and this page offers the upgrade.
 */
export default async function ProfileViewsPage({ searchParams }: PageProps<"/dashboard/profile-views">) {
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const viewers = await getProfileViewers(page);

  return (
    <>
      <PageHeader
        title="Who Viewed My Profile"
        description="Members who opened your profile page, most recent first. Members who hide their profile aren't listed."
      />
      {viewers.kind === "no_profile" ? (
        <NoProfile>Create your profile to see who views it.</NoProfile>
      ) : viewers.kind === "upgrade" ? (
        <EmptyState
          icon={<EyeIcon className="size-6" />}
          title={
            viewers.viewerCount === 0
              ? "No one has viewed your profile yet"
              : `${viewers.viewerCount} ${viewers.viewerCount === 1 ? "member has" : "members have"} viewed your profile`
          }
          action={
            <Link href="/dashboard/membership" className={primaryButton}>
              See membership plans
            </Link>
          }
        >
          {viewers.message}
        </EmptyState>
      ) : viewers.page.results.length === 0 ? (
        <EmptyState icon={<EyeIcon className="size-6" />} title="No one has viewed your profile yet">
          Members who open your profile page will appear here.
        </EmptyState>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {viewers.page.results.map((item) => (
              <li key={item.profile.profile_code} className="rounded-xl border border-line bg-white p-4">
                <MemberSummary member={item.profile}>
                  <p className="mt-2 text-sm text-ink-muted">
                    Last viewed {formatDate(item.last_viewed_at)}
                    {item.visits > 1 && ` · ${item.visits} visits`}
                  </p>
                </MemberSummary>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={viewers.page.count} basePath="/dashboard/profile-views" />
        </>
      )}
    </>
  );
}
