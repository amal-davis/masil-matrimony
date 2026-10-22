import type { Metadata } from "next";

import { InterestList, validStatus } from "@/features/dashboard/components/interest-list";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { PageHeader, pageParam } from "@/features/dashboard/components/ui";
import { getReceivedInterests } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Interests Received" };

export default async function ReceivedInterestsPage({ searchParams }: PageProps<"/dashboard/interests/received">) {
  const query = await searchParams;
  const status = validStatus("received", query.status);
  const page = pageParam(query.page);
  const data = await getReceivedInterests(page, status || undefined);

  return (
    <>
      <PageHeader title="Interests Received" description="Members who would like to connect with you. Accept to show mutual interest, or decline politely." />
      {data ? (
        <InterestList direction="received" data={data} status={status} page={page} />
      ) : (
        <NoProfile>Members can send you interests once your profile is created and approved.</NoProfile>
      )}
    </>
  );
}
