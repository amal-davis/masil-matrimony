import type { Metadata } from "next";

import { InterestList, validStatus } from "@/features/dashboard/components/interest-list";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { PageHeader, pageParam } from "@/features/dashboard/components/ui";
import { getSentInterests } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Interests Sent" };

export default async function SentInterestsPage({ searchParams }: PageProps<"/dashboard/interests/sent">) {
  const query = await searchParams;
  const status = validStatus("sent", query.status);
  const page = pageParam(query.page);
  const data = await getSentInterests(page, status || undefined);

  return (
    <>
      <PageHeader title="Interests Sent" description="Track the interests you've sent and each member's response." />
      {data ? (
        <InterestList direction="sent" data={data} status={status} page={page} />
      ) : (
        <NoProfile>You can send interests once your profile is created and approved.</NoProfile>
      )}
    </>
  );
}
