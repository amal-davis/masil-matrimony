import { DASHBOARD_PREVIEW, STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { api } from "@/lib/api/client";

import { demoProfiles } from "./demo-profiles";
import type { HighlightedProfile, HighlightedProfilesResult } from "./types";

/** Two rows of six on desktop. The API returns at most 12. */
export const HIGHLIGHTED_PROFILE_COUNT = 12;

/** GET /profiles/highlighted/: public cards chosen by staff (backend/apps/profiles/highlights.py). */
interface HighlightedProfileDto {
  profile_code: string;
  given_name: string;
  gender: "male" | "female";
  age: number;
  education: string;
  location: { city: string; district: string; state: string };
  photo: { url: string; width: number; height: number } | null;
}

const orUndefined = (value: string) => value || undefined;

function toHighlightedProfile(dto: HighlightedProfileDto): HighlightedProfile {
  return {
    id: dto.profile_code,
    profileCode: dto.profile_code,
    displayName: dto.given_name,
    gender: dto.gender,
    age: dto.age,
    education: dto.education,
    location: { city: orUndefined(dto.location.city), district: orUndefined(dto.location.district), state: dto.location.state },
    photo: dto.photo,
  };
}

/**
 * Profiles for the homepage "Highlighted Profiles" section, from the API: only
 * profiles staff highlighted whose members agreed to be featured, already
 * filtered by the backend. Not cached, so a profile removed in the admin
 * disappears on the next page load. Throws when the API can't be reached; the
 * section then hides itself rather than showing anything else.
 *
 * The static design preview (GitHub Pages, dashboard preview builds) has no API,
 * so it shows the labelled sample profiles instead.
 */
export async function getHighlightedProfiles(limit = HIGHLIGHTED_PROFILE_COUNT): Promise<HighlightedProfilesResult> {
  if (STATIC_EXPORT || DASHBOARD_PREVIEW) {
    return { profiles: demoProfiles.slice(0, limit), source: "demo" };
  }
  const data = await api.get<HighlightedProfileDto[]>(`/profiles/highlighted/?limit=${limit}`, { cache: "no-store" });
  return { profiles: (Array.isArray(data) ? data : []).slice(0, limit).map(toHighlightedProfile), source: "api" };
}
