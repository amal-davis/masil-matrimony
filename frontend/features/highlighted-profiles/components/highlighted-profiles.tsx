import Link from "next/link";

import { Container } from "@/components/ui/container";
import { SEARCH_RESULTS_PATH } from "@/features/partner-search/schema";
import { profilePath } from "@/features/profiles/paths";

import { getHighlightedProfiles, HIGHLIGHTED_PROFILE_COUNT } from "../api";
import type { HighlightedProfilesResult } from "../types";
import { ProfileCard } from "./profile-card";

/**
 * Homepage "Highlighted Profiles" section: two rows of six profile cards and a link to
 * search. Renders nothing when there are no profiles to show or loading fails,
 * so a profiles outage never breaks the homepage.
 */
export async function HighlightedProfiles() {
  let result: HighlightedProfilesResult;
  try {
    result = await getHighlightedProfiles(HIGHLIGHTED_PROFILE_COUNT);
  } catch (error) {
    console.error("Failed to load highlighted profiles", error);
    return null;
  }
  const { profiles, source } = result;
  if (profiles.length === 0) return null;

  return (
    <section aria-labelledby="highlighted-profiles-title" className="bg-white py-14 sm:py-20">
      <Container size="wide">
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="highlighted-profiles-title" className="text-3xl font-semibold sm:text-4xl">
            Highlighted Profiles
          </h2>
          <p className="mt-3 text-lg text-ink-muted">
            Discover profiles selected to help you find meaningful connections.
          </p>
          {source === "demo" && (
            <p className="mt-4 inline-flex rounded-full border border-accent-400 bg-accent-100 px-3 py-1 text-sm text-ink">
              Sample profiles for preview. Real member profiles will appear here.
            </p>
          )}
        </div>

        <ul className="mt-10 grid auto-rows-fr grid-cols-2 gap-3 sm:gap-5 md:grid-cols-3 lg:grid-cols-6 lg:gap-4 xl:gap-5">
          {profiles.map((profile) => (
            <li key={profile.id} className="min-w-0">
              <ProfileCard profile={profile} href={profilePath(profile.profileCode)} />
            </li>
          ))}
        </ul>

        <div className="mt-10 flex justify-center">
          <Link
            href={SEARCH_RESULTS_PATH}
            className="inline-flex h-12 items-center justify-center rounded-md border border-wine-600 px-7 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-wine-600 hover:text-white focus-visible:outline-wine-600"
          >
            View All Profiles
          </Link>
        </div>
      </Container>
    </section>
  );
}

/** Loading placeholder with the same footprint as the loaded grid. */
export function HighlightedProfilesSkeleton() {
  return (
    <div aria-hidden="true" className="bg-white py-14 sm:py-20">
      <Container size="wide">
        <div className="mx-auto h-24 max-w-md rounded-lg bg-surface-muted" />
        <div className="mt-10 grid grid-cols-2 gap-3 sm:gap-5 md:grid-cols-3 lg:grid-cols-6 lg:gap-4 xl:gap-5">
          {Array.from({ length: HIGHLIGHTED_PROFILE_COUNT }, (_, i) => (
            <div key={i} className="aspect-[4/6] rounded-xl bg-surface-muted" />
          ))}
        </div>
      </Container>
    </div>
  );
}
