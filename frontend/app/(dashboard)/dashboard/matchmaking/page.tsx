import type { Metadata } from "next";
import Link from "next/link";

import { MatchmakingCase } from "@/features/dashboard/components/matchmaking-case";
import { LifebuoyIcon, UserCheckIcon } from "@/features/dashboard/components/icons";
import { EmptyState, PageHeader, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";
import { getAssistanceCase, getMembership } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Matchmaking Service" };

/**
 * The member's matchmaking case: the Platinum assisted-matchmaking service
 * (opened when the membership is activated) or a Gold/Diamond assistance
 * request. Everything shown comes from the API for the signed-in member only.
 */
export default async function MatchmakingPage() {
  const membership = await getMembership();
  const requests = membership.assistance?.requests ?? [];
  const latest = requests.find((item) => item.kind === "service") ?? requests[0];
  const item = latest ? await getAssistanceCase(latest.id) : null;

  return (
    <>
      <PageHeader
        title="Matchmaking Service"
        description="Your matchmaker's progress, suggested profiles and contact coordination."
        actions={
          <Link href="/dashboard/help" className={secondaryButton}>
            <LifebuoyIcon className="size-4.5" />
            Contact the service team
          </Link>
        }
      />
      {item ? (
        <MatchmakingCase item={item} />
      ) : (
        <EmptyState
          icon={<UserCheckIcon className="size-6" />}
          title="You don't have a matchmaking case"
          action={
            <Link href="/dashboard/membership" className={primaryButton}>
              See membership plans
            </Link>
          }
        >
          Platinum Assisted Matchmaking includes a dedicated matchmaker. Gold and Diamond members can ask for
          matchmaking assistance from the membership page.
        </EmptyState>
      )}
    </>
  );
}
