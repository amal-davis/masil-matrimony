import Link from "next/link";

import { CheckIcon, LockIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import type { Entitlements } from "../types";

type Row = { label: string; on: boolean; detail?: string; href?: string; unavailable?: boolean };

/**
 * What the member's membership includes right now, exactly as the API decided
 * (GET /memberships/me/ or /dashboard/summary/ `entitlements`). Nothing here is
 * worked out from the plan name: a feature shows as included only when the
 * backend says so, and the backend enforces it on every request anyway.
 */
export function entitlementRows(entitlements: Entitlements): Row[] {
  const { features } = entitlements;
  const unavailable = (feature: Entitlements["unavailable"][number]) => entitlements.unavailable.includes(feature);
  const contacts =
    entitlements.contact_view_limit !== null
      ? `${entitlements.contact_views_remaining ?? 0} of ${entitlements.contact_view_limit} left`
      : undefined;
  const interests =
    entitlements.outgoing_interest_limit !== null
      ? `${entitlements.outgoing_interests_used ?? 0} of ${entitlements.outgoing_interest_limit} used`
      : undefined;
  return [
    { label: "Advanced search", on: features.advanced_search, href: "/search" },
    {
      label: features.unlimited_interests ? "Unlimited interests" : "Interests",
      on: true,
      detail: interests,
      href: "/dashboard/interests/sent",
    },
    { label: "Personal messaging", on: features.messaging, href: "/dashboard/messages" },
    { label: "Full profiles and photo viewing", on: features.photo_viewing },
    { label: "Profile shortlist", on: features.shortlist, href: "/dashboard/shortlisted" },
    { label: "Who viewed my profile", on: features.profile_viewers, href: "/dashboard/profile-views" },
    { label: "Match suggestions", on: features.match_suggestions, href: "/dashboard/matches" },
    { label: "Verified Profile badge (on request)", on: features.verification },
    { label: "Member contact numbers", on: features.contact_access, detail: contacts },
    {
      label: "Priority profile visibility",
      on: features.priority_visibility,
      unavailable: unavailable("priority_visibility"),
      detail: !features.priority_visibility
        ? undefined
        : unavailable("priority_visibility")
          ? "Currently unavailable"
          : "Shown ahead of other members in search results and among equally good matches",
    },
    {
      label: "Matchmaking assistance",
      on: features.matchmaking_assistance,
      unavailable: unavailable("matchmaking_assistance"),
      detail: features.matchmaking_assistance && unavailable("matchmaking_assistance") ? "Currently unavailable" : undefined,
    },
  ];
}

export function EntitlementList({ entitlements, className }: { entitlements: Entitlements; className?: string }) {
  return (
    <ul className={cn("flex flex-col gap-2.5", className)}>
      {entitlementRows(entitlements).map((row) => (
        <li key={row.label} className="flex items-start gap-2.5 text-[0.9375rem]">
          <span
            aria-hidden="true"
            className={cn(
              "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full",
              row.on ? "bg-success/10 text-success" : "bg-surface-muted text-ink-muted",
            )}
          >
            {row.on ? <CheckIcon className="size-3.5" /> : <LockIcon className="size-3" />}
          </span>
          <span className="min-w-0 flex-1">
            {row.on && row.href ? (
              <Link href={row.href} className="font-medium text-ink underline-offset-4 hover:underline">
                {row.label}
              </Link>
            ) : (
              <span className={row.on ? "font-medium" : "text-ink-muted"}>{row.label}</span>
            )}
            <span className="sr-only">
              {row.on ? (row.unavailable ? ": included, currently unavailable" : ": included") : ": not included in your plan"}
            </span>
            {row.detail && <span className="block text-sm text-ink-muted tabular-nums">{row.detail}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
