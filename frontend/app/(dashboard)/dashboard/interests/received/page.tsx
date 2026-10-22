import type { Metadata } from "next";
import { Suspense } from "react";

import { StaticInterestList } from "@/features/dashboard/components/interest-list-static";
import { InterestList, validStatus } from "@/features/dashboard/components/interest-list";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { PageHeader, pageParam } from "@/features/dashboard/components/ui";
import { previewReceived } from "@/features/dashboard/preview";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getReceivedInterests } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Interests Received" };

const header = (
  <PageHeader
    title="Interests Received"
    description="Members who would like to connect with you. Accept to show mutual interest, or decline politely."
  />
);

export default async function ReceivedInterestsPage({ searchParams }: PageProps<"/dashboard/interests/received">) {
  // Static preview (GitHub Pages): filter the sample data in the browser.
  if (STATIC_EXPORT) {
    return (
      <>
        {header}
        <Suspense fallback={null}>
          <StaticInterestList direction="received" items={previewReceived} />
        </Suspense>
      </>
    );
  }

  const query = await searchParams;
  const status = validStatus("received", query.status);
  const page = pageParam(query.page);
  const data = await getReceivedInterests(page, status || undefined);

  return (
    <>
      {header}
      {data ? (
        <InterestList direction="received" data={data} status={status} page={page} />
      ) : (
        <NoProfile>Members can send you interests once your profile is created and approved.</NoProfile>
      )}
    </>
  );
}
