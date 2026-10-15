import Image from "next/image";
import Link from "next/link";

import { VerifiedIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import type { HighlightedProfile } from "../types";

// Photo on top, details below. Cards are ~150–215px wide in the 6-across desktop rows.
const photoSizes = "(min-width: 1024px) 220px, (min-width: 768px) 30vw, 50vw";

/** Soft hyphen in the middle of long words, so a name like Thiruvananthapuram breaks as "Thiruvanan-thapuram" only if it must. */
function allowHyphenation(text: string) {
  return text.replace(/\p{L}{13,}/gu, (word) => {
    const middle = Math.ceil(word.length / 2) + 1;
    return `${word.slice(0, middle)}\u00AD${word.slice(middle)}`;
  });
}

function formatLocation({ city, district, state }: HighlightedProfile["location"]) {
  return allowHyphenation([city ?? district, state].filter(Boolean).join(", "));
}

/**
 * Public profile card. Pass `href` once a profile page exists; until then the
 * card is not interactive (there is nowhere real to send people).
 */
export function ProfileCard({ profile, href }: { profile: HighlightedProfile; href?: string }) {
  const content = (
    <>
      <div className="relative aspect-[4/5] w-full shrink-0 overflow-hidden bg-mist">
        {profile.photo ? (
          <Image
            src={profile.photo.url}
            alt={`Photo of ${profile.displayName}`}
            fill
            sizes={photoSizes}
            className="object-cover"
          />
        ) : (
          <PhotoPlaceholder />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1 p-3 sm:p-4 lg:p-3 xl:p-3.5">
        <h3 className="flex min-w-0 items-center gap-1.5 font-sans text-base font-semibold text-ink sm:text-lg lg:text-base xl:text-[1.0625rem]">
          <span className="truncate">{profile.displayName}</span>
          {profile.isVerified && (
            <>
              <VerifiedIcon className="size-5 shrink-0 text-success" />
              <span className="sr-only">, verified profile</span>
            </>
          )}
        </h3>
        <p className="text-sm text-ink-muted sm:text-[0.9375rem] lg:text-sm">
          {profile.age} years
          <span aria-hidden="true"> · </span>
          <span className="sr-only">, </span>
          <span className="break-words">{profile.education}</span>
        </p>
        <p className="mt-0.5 min-w-0 text-sm font-medium break-words text-ink sm:text-[0.9375rem] lg:text-sm">
          <span className="sr-only">Location: </span>
          {formatLocation(profile.location)}
        </p>
      </div>
    </>
  );

  const cardClasses =
    "flex h-full flex-col overflow-hidden rounded-xl border border-line bg-white transition-colors duration-200";

  return href ? (
    <Link
      href={href}
      className={cn(cardClasses, "hover:border-field-line focus-visible:outline-wine-600")}
      aria-label={`View ${profile.displayName}'s profile`}
    >
      {content}
    </Link>
  ) : (
    <article className={cn(cardClasses, "hover:border-field-line/70")} aria-label={profile.displayName}>
      {content}
    </article>
  );
}

/** Neutral portrait used when a profile has no public photo. */
function PhotoPlaceholder() {
  return (
    <div className="absolute inset-0 flex items-end justify-center bg-gradient-to-b from-mist to-brand-100">
      <svg aria-hidden="true" viewBox="0 0 120 150" className="h-[82%] w-auto text-brand-200">
        <circle cx="60" cy="52" r="26" fill="currentColor" />
        <path d="M10 150c2-33 23-55 50-55s48 22 50 55Z" fill="currentColor" />
      </svg>
      <span className="sr-only">No public photo</span>
    </div>
  );
}
