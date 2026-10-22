import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense, type ReactNode } from "react";

import { Container } from "@/components/ui/container";
import { InfoIcon, LockIcon, MapPinIcon, UsersIcon, VerifiedIcon } from "@/components/ui/icons";
import { loginUrl } from "@/features/auth/constants";
import type { MemberProfileDetail } from "@/features/dashboard/types";
import { getPrerenderedProfileCodes, getProfile, normaliseProfileCode } from "@/features/profiles/api";
import { getMemberProfile } from "@/features/profiles/member-api";
import type { ProfileDetail } from "@/features/profiles/types";
import { BriefcaseIcon, GraduationCapIcon, LanguageIcon } from "@/features/profiles/components/icons";
import { ProfileActions } from "@/features/profiles/components/profile-actions";
import { ProfileGallery } from "@/features/profiles/components/profile-gallery";
import {
  careerDetails,
  DetailList,
  familyDetails,
  hasDetails,
  hasLifestyle,
  Lifestyle,
  partnerDetails,
  personalDetails,
  ProfileSection,
} from "@/features/profiles/components/profile-sections";
import { formatHeightShort, formatLocation } from "@/features/profiles/format";
import { profilePath } from "@/features/profiles/paths";

/**
 * Sample profiles are prerendered; any other code renders on its first request.
 * Cache Components needs at least one value, so with no sample profiles a
 * placeholder is prerendered, which simply shows the not-found state.
 */
export async function generateStaticParams() {
  const codes = await getPrerenderedProfileCodes();
  return codes.length > 0 ? codes.map((id) => ({ id })) : [{ id: "__none__" }];
}

export async function generateMetadata({ params }: PageProps<"/profile/[id]">): Promise<Metadata> {
  const { id } = await params;
  const sample = await getProfile(id);
  return {
    // Real members' names stay out of titles: the title is rendered without the viewer's session.
    title: sample ? `${sample.profile.displayName} (${sample.profile.profileCode})` : `Member profile ${normaliseProfileCode(id)}`,
    // Member profiles stay out of search engines.
    robots: { index: false, follow: false },
  };
}

export default function ProfilePage({ params }: PageProps<"/profile/[id]">) {
  return (
    <Suspense fallback={<ProfileLoading />}>
      <ProfileContent params={params} />
    </Suspense>
  );
}

/**
 * Sample profiles render from the demo data (and prerender). Any other code is
 * a real member, fetched as the signed-in viewer so the API applies privacy
 * rules; that reads the session, hence the Suspense boundary above.
 */
async function ProfileContent({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sample = await getProfile(id);
  if (sample) return <ProfileView profile={sample.profile} isSample />;

  const result = await getMemberProfile(id);
  switch (result.kind) {
    case "found":
      return <ProfileView profile={result.profile} isSample={false} viewer={result.viewer} />;
    case "signed_out":
      return (
        <ProfileGate
          title="Sign in to view this profile"
          action={{ href: loginUrl(profilePath(normaliseProfileCode(id))), label: "Sign in" }}
        >
          Member profiles are visible only to registered members, to protect their privacy.
        </ProfileGate>
      );
    case "no_profile":
      return (
        <ProfileGate title="Create your profile first" action={{ href: "/dashboard/my-profile", label: "Create my profile" }}>
          Members can view other profiles once they have created their own.
        </ProfileGate>
      );
    default:
      notFound();
  }
}

function ProfileGate({ title, action, children }: { title: string; action: { href: string; label: string }; children: ReactNode }) {
  return (
    <div className="bg-mist">
      <Container className="py-14 sm:py-20">
        <div className="mx-auto max-w-lg rounded-xl border border-line bg-white px-6 py-10 text-center sm:px-10">
          <span aria-hidden="true" className="mx-auto flex size-14 items-center justify-center rounded-full bg-brand-50 text-wine-600">
            <LockIcon className="size-7" />
          </span>
          <h1 className="mt-5 text-2xl font-semibold sm:text-3xl">{title}</h1>
          <p className="mt-3 text-base leading-relaxed text-pretty text-ink-muted">{children}</p>
          <Link
            href={action.href}
            className="mt-8 inline-flex h-12 items-center justify-center rounded-md bg-wine-600 px-6 text-base font-medium text-white transition-colors hover:bg-wine-800 focus-visible:outline-wine-600"
          >
            {action.label}
          </Link>
        </div>
      </Container>
    </div>
  );
}

function ProfileLoading() {
  return (
    <div className="bg-mist" role="status" aria-label="Loading profile">
      <Container size="wide" className="py-6 sm:py-10 lg:py-14">
        <div className="mt-8 h-[28rem] animate-pulse rounded-xl bg-white motion-reduce:animate-none" />
      </Container>
    </div>
  );
}

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <span aria-hidden="true" className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-wine-600">
        {icon}
      </span>
      <div className="min-w-0">
        <dt className="text-sm text-ink-muted">{label}</dt>
        <dd className="font-medium break-words text-ink">{children}</dd>
      </div>
    </div>
  );
}

function ProfileView({
  profile,
  isSample,
  viewer,
}: {
  profile: ProfileDetail;
  isSample: boolean;
  viewer?: MemberProfileDetail["viewer"];
}) {
  const path = profilePath(profile.profileCode);
  const summary = [
    `${profile.age} years`,
    profile.heightCm && formatHeightShort(profile.heightCm),
    profile.maritalStatus,
  ].filter(Boolean);
  const faith = [profile.religion, profile.community].filter(Boolean).join(" · ");
  const career = careerDetails(profile);
  const family = familyDetails(profile);
  const partner = partnerDetails(profile);

  return (
    <div className="bg-mist">
      {/* The wide container (up to 88rem): biodata cards in two columns need the room. */}
      <Container size="wide" className="py-6 sm:py-10 lg:py-14">
        <nav aria-label="Breadcrumb" className="text-sm text-ink-muted">
          <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <li>
              <Link href="/" className="rounded-sm hover:text-wine-600 hover:underline focus-visible:outline-wine-600">
                Home
              </Link>
            </li>
            <li aria-hidden="true">/</li>
            <li>
              <Link href="/search" className="rounded-sm hover:text-wine-600 hover:underline focus-visible:outline-wine-600">
                Search
              </Link>
            </li>
            <li aria-hidden="true">/</li>
            <li aria-current="page" className="font-medium text-ink">
              {profile.profileCode}
            </li>
          </ol>
        </nav>

        {isSample && (
          <p className="mt-4 flex items-start gap-2.5 rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-[0.9375rem] text-ink">
            <InfoIcon className="mt-0.5 size-5 shrink-0 text-accent-600" />
            <span>
              <strong className="font-semibold">Sample profile for preview.</strong> This is fictional data, not a real
              member. Real member profiles will appear here.
            </span>
          </p>
        )}

        {/*
          Header. Source order is name, photo, details: phones show who this is first, then the
          photo, then the facts. From md the photo moves to a left column spanning both rows.
        */}
        <section
          aria-labelledby="profile-name"
          className="mt-4 grid gap-x-6 gap-y-5 rounded-xl border border-line bg-white p-4 sm:mt-6 sm:p-6 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:grid-rows-[auto_1fr] lg:gap-x-10 lg:p-8"
        >
          <div className="min-w-0 md:col-start-2 md:row-start-1">
            <p className="inline-flex rounded-full border border-line bg-mist px-3 py-1 text-sm text-ink-muted">
              Profile ID:&nbsp;<span className="font-semibold tracking-wide text-ink">{profile.profileCode}</span>
            </p>
            <h1
              id="profile-name"
              className="mt-3 flex flex-wrap items-center gap-x-2 text-[2rem] leading-tight font-semibold break-words sm:text-4xl"
            >
              {profile.displayName}
              {profile.isVerified && (
                <>
                  <VerifiedIcon className="size-7 shrink-0 text-success" />
                  <span className="sr-only">, verified profile</span>
                </>
              )}
            </h1>
            <p className="mt-1.5 text-lg text-ink-muted">{summary.join(" · ")}</p>
          </div>

          <div className="mx-auto w-full max-w-64 min-[400px]:max-w-72 sm:max-w-80 md:col-start-1 md:row-span-2 md:row-start-1 md:max-w-none">
            {/* Only what the gallery needs crosses to the browser, and hidden photos never do. */}
            <ProfileGallery
              profile={{
                id: profile.id,
                gender: profile.gender,
                displayName: profile.displayName,
                photos: profile.photosHidden ? [] : profile.photos,
                photosHidden: profile.photosHidden,
              }}
            />
          </div>

          <div className="min-w-0 md:col-start-2 md:row-start-2">
            <dl className="grid gap-x-6 gap-y-4 border-t border-line pt-6 sm:grid-cols-2">
              {faith && (
                <Fact icon={<UsersIcon className="size-5" />} label="Religion & Community">
                  {faith}
                </Fact>
              )}
              <Fact icon={<GraduationCapIcon className="size-5" />} label="Education">
                {profile.education}
              </Fact>
              {(profile.career?.profession ?? profile.profession) && (
                <Fact icon={<BriefcaseIcon className="size-5" />} label="Profession">
                  {profile.career?.profession ?? profile.profession}
                </Fact>
              )}
              <Fact icon={<MapPinIcon className="size-5" />} label="Location">
                {formatLocation(profile.location)}
              </Fact>
              {profile.motherTongue && (
                <Fact icon={<LanguageIcon className="size-5" />} label="Mother Tongue">
                  {profile.motherTongue}
                </Fact>
              )}
            </dl>

            <div className="mt-6 border-t border-line pt-6">
              <ProfileActions
                profilePath={path}
                profileCode={profile.profileCode}
                displayName={profile.displayName}
                isSample={isSample}
                viewer={viewer}
              />
            </div>
          </div>
        </section>

        {/* Biodata: two columns of cards from lg, one column before. */}
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <ProfileSection id="about" title="About Me" className="lg:col-span-2">
            <p className="max-w-[72ch] text-base leading-relaxed text-pretty whitespace-pre-line text-ink sm:text-[1.0625rem]">
              {profile.about?.trim() || "This member has not added an introduction yet."}
            </p>
          </ProfileSection>

          <ProfileSection id="personal" title="Personal Details">
            <DetailList items={personalDetails(profile)} />
          </ProfileSection>

          <ProfileSection id="career" title="Education & Career">
            <DetailList items={career} />
          </ProfileSection>

          {hasDetails(family) && (
            <ProfileSection id="family" title="Family Background">
              <DetailList items={family} />
            </ProfileSection>
          )}

          {profile.lifestyle && hasLifestyle(profile) && (
            <ProfileSection id="lifestyle" title="Lifestyle & Interests">
              <Lifestyle lifestyle={profile.lifestyle} />
            </ProfileSection>
          )}

          {(hasDetails(partner) || profile.partnerPreferences?.notes) && (
            <ProfileSection id="partner" title="Partner Preferences" className="lg:col-span-2">
              <DetailList items={partner} className="lg:grid-cols-3" />
              {profile.partnerPreferences?.notes && (
                <p className="mt-5 max-w-[72ch] text-base leading-relaxed text-ink">
                  {profile.partnerPreferences.notes}
                </p>
              )}
            </ProfileSection>
          )}
        </div>
      </Container>
    </div>
  );
}
