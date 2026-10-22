import Link from "next/link";

import { formatDate } from "../format";
import type { InterestItem, Paginated } from "../types";
import { InboxIcon, SendIcon } from "./icons";
import { InterestCard } from "./interest-card";
import { EmptyState, LinkTabs, Pagination, primaryButton } from "./ui";

const filters = {
  received: [
    { value: "", label: "All" },
    { value: "pending", label: "Awaiting your reply" },
    { value: "accepted", label: "Accepted" },
    { value: "declined", label: "Declined" },
  ],
  sent: [
    { value: "", label: "All" },
    { value: "pending", label: "Awaiting response" },
    { value: "accepted", label: "Accepted" },
    { value: "declined", label: "Declined" },
    { value: "withdrawn", label: "Withdrawn" },
  ],
};

export const validStatus = (direction: "received" | "sent", value: string | string[] | undefined) => {
  const status = Array.isArray(value) ? value[0] : value;
  return filters[direction].some((filter) => filter.value === status) ? (status ?? "") : "";
};

/** Status filters (in the URL, so refresh and back work), the inbox list and paging. */
export function InterestList({
  direction,
  data,
  status,
  page,
}: {
  direction: "received" | "sent";
  data: Paginated<InterestItem>;
  status: string;
  page: number;
}) {
  const basePath = `/dashboard/interests/${direction}`;
  const shown = filters[direction].find((filter) => filter.value === status)?.label ?? "All";

  return (
    <>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <LinkTabs
          label="Filter by status"
          tabs={filters[direction].map((filter) => ({
            href: filter.value ? `${basePath}?status=${filter.value}` : basePath,
            label: filter.label,
            active: filter.value === status,
          }))}
        />
        <p className="text-sm text-ink-muted" aria-live="polite">
          {data.count} {data.count === 1 ? "interest" : "interests"}
          {status ? ` · ${shown.toLowerCase()}` : ""}
        </p>
      </div>

      {data.results.length === 0 ? (
        <EmptyState
          icon={direction === "received" ? <InboxIcon className="size-6" /> : <SendIcon className="size-6" />}
          title={status ? "Nothing here" : direction === "received" ? "No interests received yet" : "You haven't sent any interests yet"}
          action={
            status ? (
              <Link href={basePath} className={primaryButton}>
                Show all interests
              </Link>
            ) : direction === "sent" ? (
              <Link href="/dashboard/matches" className={primaryButton}>
                Find matches
              </Link>
            ) : (
              <Link href="/dashboard/my-profile" className={primaryButton}>
                Strengthen my profile
              </Link>
            )
          }
        >
          {status
            ? "No interests have this status."
            : direction === "received"
              ? "When members are interested in your profile, they'll appear here. A complete profile with a photo helps."
              : "Send an interest from a member's profile to let them know you'd like to connect."}
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-3">
          {data.results.map((item) => (
            <InterestCard key={item.id} item={item} direction={direction} date={formatDate(item.created_at)} />
          ))}
        </ul>
      )}

      <Pagination page={page} count={data.count} basePath={basePath} params={{ status: status || undefined }} />
    </>
  );
}
