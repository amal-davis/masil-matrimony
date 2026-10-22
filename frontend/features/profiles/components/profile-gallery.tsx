"use client";

import Image from "next/image";
import { useState } from "react";

import { LockIcon } from "@/components/ui/icons";
import { ProfileAvatar } from "@/features/highlighted-profiles/components/profile-avatar";
import { cn } from "@/lib/utils";

import type { ProfileDetail } from "../types";

const mainSizes = "(min-width: 1024px) 26rem, (min-width: 640px) 22rem, 18rem";

/** Real member photos are absolute, signed API URLs; local sample assets are paths. */
const isRemote = (url: string) => url.startsWith("http://") || url.startsWith("https://");

/**
 * The profile photo with thumbnails for any further public photos. Hidden
 * photos are never rendered; without a public photo the illustrated avatar
 * stands in (it is not a picture of the member).
 */
export function ProfileGallery({
  profile,
}: {
  profile: Pick<ProfileDetail, "id" | "gender" | "displayName" | "photos" | "photosHidden">;
}) {
  const photos = profile.photosHidden ? [] : profile.photos;
  const [index, setIndex] = useState(0);
  const photo = photos[index];

  return (
    <div>
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-lg bg-mist">
        {photo ? (
          <Image
            // Keyed so the new photo replaces the old one instead of briefly stretching it.
            key={photo.url}
            src={photo.url}
            alt={
              photos.length > 1
                ? `Photo ${index + 1} of ${photos.length} of ${profile.displayName}`
                : `Photo of ${profile.displayName}`
            }
            fill
            sizes={mainSizes}
            priority={index === 0}
            // Member photos are signed, short-lived API URLs: nothing for the optimiser to cache.
            unoptimized={isRemote(photo.url)}
            className="object-cover object-[50%_25%]"
          />
        ) : (
          <>
            <ProfileAvatar profile={profile} />
            <p className="absolute inset-x-3 bottom-3 flex items-center justify-center gap-2 rounded-md bg-white/90 px-3 py-2 text-center text-sm font-medium text-ink">
              {profile.photosHidden ? (
                <>
                  <LockIcon className="size-4 shrink-0 text-wine-600" />
                  Photos are kept private by this member
                </>
              ) : (
                "No photo added yet"
              )}
            </p>
          </>
        )}
      </div>

      {photos.length > 1 && (
        <ul className="mt-3 grid grid-cols-5 gap-2" aria-label="More photos">
          {photos.map((item, i) => (
            <li key={item.url}>
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Show photo ${i + 1} of ${photos.length}`}
                aria-pressed={i === index}
                className={cn(
                  "relative block aspect-square w-full overflow-hidden rounded-md border-2 transition-colors focus-visible:outline-wine-600",
                  i === index ? "border-wine-600" : "border-transparent hover:border-field-line",
                )}
              >
                <Image src={item.url} alt="" fill sizes="5rem" unoptimized={isRemote(item.url)} className="object-cover object-[50%_25%]" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
