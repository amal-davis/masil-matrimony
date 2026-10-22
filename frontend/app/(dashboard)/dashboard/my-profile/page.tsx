import type { Metadata } from "next";
import Link from "next/link";

import { CreateProfileForm } from "@/features/dashboard/components/create-profile-form";
import { EyeIcon } from "@/features/dashboard/components/icons";
import { MemberPhoto } from "@/features/dashboard/components/member-photo";
import { ProfileEditor } from "@/features/dashboard/components/profile-editor";
import { SectionTabs } from "@/features/dashboard/components/section-tabs";
import { SubmitReview } from "@/features/dashboard/components/submit-review";
import { Badge, Notice, PageHeader, ProgressBar, secondaryButton } from "@/features/dashboard/components/ui";
import { profileStatus } from "@/features/dashboard/format";
import { PROFILE_SECTION_TABS } from "@/features/dashboard/profile-section-tabs";
import { getDashboardSummary, getOwnPhotos, getOwnProfile } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "My Profile" };

export default async function MyProfilePage() {
  const profile = await getOwnProfile("/dashboard/my-profile");

  if (!profile) {
    const { member } = await getDashboardSummary();
    return (
      <>
        <PageHeader title="My Profile" description="Your matrimonial profile, as families will see it." />
        <CreateProfileForm defaultName={member.first_name} />
      </>
    );
  }

  const photos = await getOwnPhotos();
  const primary = photos.find((photo) => photo.is_primary) ?? null;
  const status = profileStatus[profile.status];
  const canSubmit = profile.status === "draft" || profile.status === "rejected";

  return (
    <>
      <PageHeader
        title="My Profile"
        description="Keep your details accurate and up to date. Each section saves on its own."
        actions={
          <Link href={`/profile/${profile.profile_code}`} className={secondaryButton}>
            <EyeIcon className="size-4.5" />
            Preview as members see it
          </Link>
        }
      />

      {/* Profile summary */}
      <section aria-label="Profile summary" className="mb-6 rounded-xl border border-line bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            <MemberPhoto
              photo={primary ? { url: primary.url, width: primary.width, height: primary.height } : null}
              name={profile.display_name}
              seed={profile.profile_code}
              gender={profile.gender}
              className="aspect-[4/5] w-20 shrink-0 rounded-lg ring-1 ring-line"
            />
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold">{profile.display_name}</p>
              <p className="text-sm text-ink-muted">
                Matrimony ID <span className="font-semibold tracking-wide text-ink">{profile.profile_code}</span>
              </p>
              <div className="mt-2">
                <Badge tone={status.tone}>{status.label}</Badge>
              </div>
            </div>
          </div>
          <div className="md:w-72">
            <ProgressBar value={profile.completion.percent} label="Profile completion" />
            {canSubmit && profile.missing_for_review.length > 0 && (
              <p className="mt-2 text-sm text-ink-muted">
                Needed to submit: <span className="text-ink">{profile.missing_for_review.join(", ")}</span>
              </p>
            )}
          </div>
          {canSubmit && profile.missing_for_review.length === 0 && (
            <div className="md:shrink-0">
              <SubmitReview resubmit={profile.status === "rejected"} />
            </div>
          )}
        </div>
        {profile.status === "rejected" && profile.review_note && (
          <Notice tone="danger" className="mt-4">
            <strong className="font-semibold">Changes requested:</strong> {profile.review_note}
          </Notice>
        )}
        {profile.status === "pending_review" && (
          <Notice className="mt-4">
            Our team is reviewing your profile. You can keep editing everything except your name, gender and date of birth.
          </Notice>
        )}
      </section>

      <SectionTabs
        label="Profile sections"
        sections={[...PROFILE_SECTION_TABS]}
      />

      <ProfileEditor profile={profile} />
    </>
  );
}
