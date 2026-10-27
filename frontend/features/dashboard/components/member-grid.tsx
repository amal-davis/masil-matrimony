import Link from "next/link";
import type { ReactNode } from "react";

import { CheckIcon, MapPinIcon, UsersIcon } from "@/components/ui/icons";
import { BriefcaseIcon, GraduationCapIcon } from "@/features/profiles/components/icons";
import { formatHeightShort } from "@/features/profiles/format";
import { profilePath } from "@/features/profiles/paths";
import { cn } from "@/lib/utils";

import { formatMemberLocation } from "../format";
import type { MatchInfo, MemberCard as MemberCardData } from "../types";
import { MemberPhoto } from "./member-photo";
import { VerifiedBadge } from "./verified-badge";
import { HideMatchButton } from "./hide-match-button";
import { ShortlistButton } from "./shortlist-button";

function Fact({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex min-w-0 items-start gap-2">
      <span aria-hidden="true" className="mt-0.5 shrink-0 text-ink-muted">
        {icon}
      </span>
      <span className="min-w-0 break-words">{children}</span>
    </li>
  );
}

/**
 * "86% match" over the photo, and "Mutual" when the member also meets this profile's
 * must-haves. Visual only: the photo link is hidden from screen readers, so the card
 * body repeats this as text (matchSummary).
 */
function MatchBadges({ match }: { match: MatchInfo }) {
  if (match.score === null && !match.mutual) return null;
  return (
    <div className="pointer-events-none absolute top-2 left-2 flex flex-wrap gap-1.5">
      {match.score !== null && (
        <span className="rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-wine-600 shadow-sm tabular-nums">
          {match.score}% match
        </span>
      )}
      {match.mutual && (
        <span className="rounded-full bg-wine-600/95 px-2.5 py-1 text-xs font-semibold text-white shadow-sm">Mutual</span>
      )}
    </div>
  );
}

const matchSummary = (match: MatchInfo) =>
  [
    match.score !== null ? `${match.score}% match with your partner preferences.` : "",
    match.mutual ? "Mutual: you also meet this member's must-haves." : "",
  ]
    .filter(Boolean)
    .join(" ");

/**
 * A matrimonial profile card for the portal: 4:5 photo (or the illustrated
 * avatar), name and age, the facts families look for first, and actions in a
 * footer kept outside the profile links (no nested interactive elements).
 * With `match` (the matches list) it also shows the score and why it matched.
 */
export function MemberProfileCard({
  member,
  shortlisted,
  compact = false,
  match,
}: {
  member: MemberCardData;
  shortlisted: boolean;
  compact?: boolean;
  match?: MatchInfo;
}) {
  const href = profilePath(member.profile_code);
  const faith = [member.religion, member.community].filter(Boolean).join(" · ");
  const vitals = [`${member.age} yrs`, member.height_cm ? formatHeightShort(member.height_cm) : null, member.marital_status]
    .filter(Boolean)
    .join(" · ");
  const location = formatMemberLocation(member.location);

  return (
    <article className="group flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-line bg-white transition-colors hover:border-field-line">
      <Link href={href} tabIndex={-1} aria-hidden="true" className="relative block">
        {match && <MatchBadges match={match} />}
        <MemberPhoto
          photo={member.photo}
          name={member.display_name}
          seed={member.profile_code}
          gender={member.gender}
          hidden={member.photos_hidden}
          className="aspect-[4/5] w-full"
        />
      </Link>
      <div className={cn("flex flex-1 flex-col", compact ? "p-3.5" : "p-4")}>
        <h3 className="font-sans text-base leading-snug font-semibold text-ink">
          <Link href={href} className="rounded-sm hover:text-wine-600 focus-visible:outline-wine-600">
            {member.display_name}
          </Link>
          {member.verified && <VerifiedBadge className="ml-2 align-middle" />}
        </h3>
        <p className="mt-0.5 text-sm text-ink">{vitals}</p>
        <p className="text-xs tracking-wide text-ink-muted">
          <span className="sr-only">Member ID </span>
          {member.profile_code}
        </p>
        {match && matchSummary(match) && <p className="sr-only">{matchSummary(match)}</p>}
        {!compact && (
          <ul className="mt-3 flex flex-col gap-1.5 text-sm text-ink">
            {faith && <Fact icon={<UsersIcon className="size-4" />}>{faith}</Fact>}
            {member.education && <Fact icon={<GraduationCapIcon className="size-4" />}>{member.education}</Fact>}
            {member.occupation && <Fact icon={<BriefcaseIcon className="size-4" />}>{member.occupation}</Fact>}
            {location && <Fact icon={<MapPinIcon className="size-4" />}>{location}</Fact>}
          </ul>
        )}
        {compact && location && <p className="mt-1 truncate text-sm text-ink-muted">{location}</p>}
        {!compact && match && match.reasons.length > 0 && (
          <div className="mt-3 rounded-lg bg-mist px-3 py-2.5">
            <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">Why it&apos;s a match</p>
            <ul className="mt-1.5 flex flex-col gap-1 text-sm text-ink">
              {match.reasons.slice(0, 3).map((reason) => (
                <li key={reason} className="flex items-start gap-1.5">
                  <CheckIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                  <span className="min-w-0">{reason}</span>
                </li>
              ))}
            </ul>
            {match.reasons.length > 3 && (
              <p className="mt-1 text-xs text-ink-muted">and {match.reasons.length - 3} more</p>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-1 border-t border-line p-1.5">
        <Link
          href={href}
          className="inline-flex min-h-10 flex-1 items-center justify-center rounded-lg px-2 text-sm font-medium text-wine-600 transition-colors hover:bg-brand-50 focus-visible:outline-wine-600"
        >
          View profile
          <span className="sr-only"> of {member.display_name}</span>
        </Link>
        <ShortlistButton profileCode={member.profile_code} name={member.display_name} shortlisted={shortlisted} className="flex-1" />
        {match && !compact && <HideMatchButton profileCode={member.profile_code} name={member.display_name} className="flex-none" />}
      </div>
    </article>
  );
}

/** A responsive grid of profile cards: 1 column on narrow phones up to 4 on wide screens. */
export function MemberGrid({
  members,
  compact = false,
}: {
  members: (MemberCardData & { shortlisted: boolean; match?: MatchInfo })[];
  compact?: boolean;
}) {
  return (
    <ul
      className={cn(
        "grid gap-4",
        compact ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4",
      )}
    >
      {members.map((member) => (
        <li key={member.profile_code} className="min-w-0">
          <MemberProfileCard member={member} shortlisted={member.shortlisted} compact={compact} match={member.match} />
        </li>
      ))}
    </ul>
  );
}
