import type { Metadata } from "next";
import { Suspense } from "react";

import { StaticInterestList } from "@/features/dashboard/components/interest-list-static";
import { InterestList, validStatus } from "@/features/dashboard/components/interest-list";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { PageHeader, pageParam } from "@/features/dashboard/components/ui";
import { previewSent } from "@/features/dashboard/preview";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getSentInterests } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Interests Sent" };

const header = <PageHeader title="Interests Sent" description="Track the interests you've sent and each member's response." />;

export default async function SentInterestsPage({ searchParams }: PageProps<"/dashboard/interests/sent">) {
  // Static preview (GitHub Pages): filter the sample data in the browser.
  if (STATIC_EXPORT) {
    return (
      <>
        {header}
        <Suspense fallback={null}>
          <StaticInterestList direction="sent" items={previewSent} />
        </Suspense>
      </>
    );
  }

  const query = await searchParams;
  const status = validStatus("sent", query.status);
  const page = pageParam(query.page);
  const data = await getSentInterests(page, status || undefined);

  return (
    <>
      {header}
      {data ? (
        <InterestList direction="sent" data={data} status={status} page={page} />
      ) : (
        <NoProfile>You can send interests once your profile is created and approved.</NoProfile>
      )}
    </>
  );
}
