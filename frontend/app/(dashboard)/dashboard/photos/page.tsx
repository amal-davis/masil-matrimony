import type { Metadata } from "next";

import { NoProfile } from "@/features/dashboard/components/no-profile";
import { PhotoManager } from "@/features/dashboard/components/photo-manager";
import { PrivacySettings } from "@/features/dashboard/components/photo-privacy";
import { Card, PageHeader } from "@/features/dashboard/components/ui";
import { getOwnPhotos, getOwnProfile } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Manage Photos" };

export default async function PhotosPage() {
  const profile = await getOwnProfile("/dashboard/photos");

  return (
    <>
      <PageHeader
        title="Manage Photos"
        description="Every photo is checked by our team before other members can see it. You decide who sees them."
      />
      {!profile ? (
        <NoProfile>Photos belong to your profile, so start there.</NoProfile>
      ) : (
        <div className="flex flex-col gap-6">
          <PhotoManager photos={await getOwnPhotos()} maxPhotos={profile.max_photos} />
          <Card title="Photo privacy" titleId="photo-privacy-title" description="Applies to every approved photo.">
            <PrivacySettings
              initial={{ visibility: profile.visibility, photo_visibility: profile.photo_visibility }}
              showProfileVisibility={false}
            />
          </Card>
        </div>
      )}
    </>
  );
}
