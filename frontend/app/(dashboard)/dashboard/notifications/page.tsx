import type { Metadata } from "next";
import type { ReactNode } from "react";

import { CheckIcon } from "@/components/ui/icons";
import { BellIcon, CameraIcon, CrownIcon, InboxIcon, SendIcon, UserCheckIcon } from "@/features/dashboard/components/icons";
import { MarkAllRead, NotificationLink } from "@/features/dashboard/components/notification-actions";
import { Badge, EmptyState, PageHeader, pageParam, Pagination } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getNotifications } from "@/features/dashboard/server-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Notifications" };

/** Only site paths are followed; anything else in a stored link is ignored. */
const safeLink = (link: string) => (link.startsWith("/") && !link.startsWith("//") ? link : "");

const kindIcon: Record<string, ReactNode> = {
  interest_received: <InboxIcon className="size-[1.125rem]" />,
  interest_accepted: <CheckIcon className="size-[1.125rem]" />,
  interest_declined: <SendIcon className="size-[1.125rem]" />,
  profile_approved: <UserCheckIcon className="size-[1.125rem]" />,
  profile_changes_requested: <UserCheckIcon className="size-[1.125rem]" />,
  photo_approved: <CameraIcon className="size-[1.125rem]" />,
  photo_rejected: <CameraIcon className="size-[1.125rem]" />,
  membership_activated: <CrownIcon className="size-[1.125rem]" />,
};

export default async function NotificationsPage({ searchParams }: PageProps<"/dashboard/notifications">) {
  // The static preview (GitHub Pages) has no query string on the server; its sample data fits on one page.
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const data = await getNotifications(page);

  return (
    <>
      <PageHeader
        title="Notifications"
        description={
          data.unread_count > 0
            ? `${data.unread_count} unread · interests, replies, profile reviews and membership updates.`
            : "Interests, replies, profile reviews and membership updates."
        }
        actions={data.unread_count > 0 ? <MarkAllRead /> : undefined}
      />
      {data.results.length === 0 ? (
        <EmptyState icon={<BellIcon className="size-6" />} title="You're all caught up">
          When something happens with your profile or interests, you&apos;ll see it here.
        </EmptyState>
      ) : (
        <>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
            {data.results.map((item) => (
              <li
                key={item.id}
                className={cn(
                  "flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6",
                  !item.read && "bg-brand-50/40",
                )}
              >
                <div className="flex min-w-0 gap-3.5">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full",
                      item.read ? "bg-surface-muted text-ink-muted" : "bg-brand-100 text-wine-600",
                    )}
                  >
                    {kindIcon[item.kind] ?? <BellIcon className="size-[1.125rem]" />}
                  </span>
                  <div className="min-w-0">
                    <p className={cn("flex flex-wrap items-center gap-2 break-words", item.read ? "text-ink" : "font-semibold text-ink")}>
                      {item.title}
                      {!item.read && <Badge tone="brand">New</Badge>}
                    </p>
                    {item.body && <p className="mt-0.5 text-[0.9375rem] break-words text-ink-muted">{item.body}</p>}
                    <p className="mt-1 text-sm text-ink-muted">{formatDate(item.created_at)}</p>
                  </div>
                </div>
                <div className="shrink-0 pl-[3.375rem] sm:pl-0">
                  <NotificationLink id={item.id} href={safeLink(item.link)} read={item.read} />
                </div>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={data.count} basePath="/dashboard/notifications" />
        </>
      )}
    </>
  );
}
