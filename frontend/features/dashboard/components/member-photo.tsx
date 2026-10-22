import { LockIcon } from "@/components/ui/icons";
import { ProfileAvatar } from "@/features/highlighted-profiles/components/profile-avatar";
import { cn } from "@/lib/utils";

import type { PhotoRef } from "../types";

/**
 * A member's photo from a signed, short-lived API URL, or the illustrated
 * avatar when there is none (or it's private). A plain <img>: signed URLs
 * change on every request, so image optimisation would cache nothing.
 */
export function MemberPhoto({
  photo,
  name,
  seed,
  gender,
  hidden = false,
  className,
}: {
  photo: PhotoRef | null;
  name: string;
  /** Stable value (the profile code) that picks the avatar's look. */
  seed: string;
  gender?: "male" | "female";
  hidden?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("relative overflow-hidden bg-mist", className)}>
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo.url}
          alt={`Photo of ${name}`}
          width={photo.width}
          height={photo.height}
          loading="lazy"
          decoding="async"
          className="absolute inset-0 size-full object-cover object-[50%_25%]"
        />
      ) : (
        <>
          <ProfileAvatar profile={{ id: seed, gender }} />
          {hidden && (
            <span className="absolute inset-x-2 bottom-2 flex items-center justify-center gap-1.5 rounded bg-white/90 px-2 py-1 text-xs font-medium text-ink">
              <LockIcon className="size-3.5 shrink-0 text-wine-600" />
              Photo private
            </span>
          )}
        </>
      )}
    </div>
  );
}
