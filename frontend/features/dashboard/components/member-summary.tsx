import Link from "next/link";
import type { ReactNode } from "react";

import { formatHeightShort } from "@/features/profiles/format";
import { profilePath } from "@/features/profiles/paths";

import { formatMemberLocation } from "../format";
import type { OtherMember } from "../types";
import { MemberPhoto } from "./member-photo";

/** Photo, name, member ID and key facts for another member, as a horizontal row. Used in lists. */
export function MemberSummary({ member, children }: { member: OtherMember; children?: ReactNode }) {
  if (!member.available) {
    return (
      <div className="flex items-center gap-4">
        <MemberPhoto photo={null} name={member.display_name} seed={member.profile_code} className="aspect-[4/5] w-20 shrink-0 rounded-lg sm:w-24" />
        <div className="min-w-0">
          <p className="font-semibold break-words">{member.display_name}</p>
          <p className="text-sm text-ink-muted">{member.profile_code}</p>
          <p className="mt-1 text-sm text-ink-muted">This profile is no longer available.</p>
          {children}
        </div>
      </div>
    );
  }

  const facts = [
    `${member.age} yrs`,
    member.height_cm ? formatHeightShort(member.height_cm) : null,
    member.marital_status,
    [member.religion, member.community].filter(Boolean).join(" · "),
    member.education,
    member.occupation,
    formatMemberLocation(member.location),
  ].filter(Boolean);

  return (
    <div className="flex items-start gap-4">
      <Link
        href={profilePath(member.profile_code)}
        tabIndex={-1}
        aria-hidden="true"
        className="shrink-0"
      >
        <MemberPhoto
          photo={member.photo}
          name={member.display_name}
          seed={member.profile_code}
          gender={member.gender}
          hidden={member.photos_hidden}
          className="aspect-[4/5] w-20 rounded-lg sm:w-24"
        />
      </Link>
      <div className="min-w-0 flex-1">
        <Link
          href={profilePath(member.profile_code)}
          className="rounded-sm font-semibold break-words text-ink hover:text-wine-600 hover:underline focus-visible:outline-wine-600"
        >
          {member.display_name}
        </Link>
        <p className="text-sm text-ink-muted">{member.profile_code}</p>
        <p className="mt-1 text-sm leading-relaxed break-words text-ink">{facts.join(" · ")}</p>
        {children}
      </div>
    </div>
  );
}
