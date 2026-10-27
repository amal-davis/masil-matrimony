import type { Metadata } from "next";
import Link from "next/link";

import { MessagesIcon } from "@/components/ui/icons";
import { MemberPhoto } from "@/features/dashboard/components/member-photo";
import { NoProfile } from "@/features/dashboard/components/no-profile";
import { Badge, EmptyState, PageHeader, pageParam, Pagination, primaryButton } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getConversations, getMembership } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Messages" };

/** The member's conversations, latest first, from the API. Each opens its own page. */
export default async function MessagesPage({ searchParams }: PageProps<"/dashboard/messages">) {
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const [data, membership] = await Promise.all([getConversations(page), getMembership()]);
  const canStart = membership.entitlements.features.messaging;

  return (
    <>
      <PageHeader
        title="Messages"
        description="Personal messages with members whose interest you've accepted, or who accepted yours."
      />
      {!data ? (
        <NoProfile>Create your profile to message other members.</NoProfile>
      ) : data.results.length === 0 ? (
        <EmptyState
          icon={<MessagesIcon className="size-6" />}
          title="No messages yet"
          action={
            <Link href={canStart ? "/dashboard/interests/sent?status=accepted" : "/dashboard/membership"} className={primaryButton}>
              {canStart ? "See accepted interests" : "See membership plans"}
            </Link>
          }
        >
          {canStart
            ? "Open the profile of a member whose interest was accepted and choose “Send message”."
            : "Starting a conversation is included with the Silver, Gold and Diamond memberships. You can always reply to members who write to you."}
        </EmptyState>
      ) : (
        <>
          <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
            {data.results.map((item) => (
              <li key={item.profile.profile_code}>
                <Link
                  href={`/dashboard/messages/${item.profile.profile_code}`}
                  className="flex items-center gap-4 px-4 py-4 hover:bg-mist focus-visible:outline-wine-600 sm:px-5"
                >
                  <MemberPhoto
                    photo={item.profile.available ? item.profile.photo : null}
                    name={item.profile.display_name}
                    seed={item.profile.profile_code}
                    gender={item.profile.available ? item.profile.gender : undefined}
                    className="size-12 shrink-0 rounded-full"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="truncate font-semibold text-ink">{item.profile.display_name}</span>
                      <span className="shrink-0 text-sm text-ink-muted">{formatDate(item.updated_at)}</span>
                    </span>
                    <span className="mt-0.5 flex items-center justify-between gap-3">
                      <span className={item.unread ? "truncate text-sm font-medium text-ink" : "truncate text-sm text-ink-muted"}>
                        {item.last_message ? `${item.last_message.mine ? "You: " : ""}${item.last_message.body}` : ""}
                      </span>
                      {item.unread > 0 && <Badge tone="brand">{item.unread} new</Badge>}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={data.count} basePath="/dashboard/messages" />
        </>
      )}
    </>
  );
}
