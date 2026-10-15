import { demoProfiles } from "./demo-profiles";
import type { HighlightedProfilesResult } from "./types";

/** Two rows of six on desktop. */
export const HIGHLIGHTED_PROFILE_COUNT = 12;

/**
 * Demo profiles are fictional, so they must never reach real visitors by
 * accident: they show in development, or in a production build only when
 * NEXT_PUBLIC_SHOW_DEMO_PROFILES=true is set deliberately (e.g. a staging demo).
 */
const demoAllowed =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_SHOW_DEMO_PROFILES === "true";

/**
 * Profiles for the homepage "Highlighted Profiles" section.
 *
 * NOT CONNECTED: the backend has no profiles API yet. When it exists, replace
 * the body with a call through the shared client, e.g.
 *
 *   const data = await api.get<HighlightedProfileDto[]>(`/profiles/highlighted/?limit=${limit}`);
 *   return { profiles: data.map(toHighlightedProfile), source: "api" };
 *
 * Expected response (planned, not implemented): an array of public profile
 * cards, already filtered by the backend to approved, publicly visible,
 * active profiles:
 *
 *   [{ "public_id": "uuid", "profile_code": "MM100234", "display_name": "Anjali",
 *      "age": 25, "education": "M.Sc.",
 *      "location": { "city": null, "district": "Thrissur", "state": "Kerala" },
 *      "primary_photo": { "url": "https://…", "width": 800, "height": 1000 } | null,
 *      "is_verified": true }]
 *
 * Remote photo hosts then need adding to `images.remotePatterns` in next.config.ts.
 */
export async function getHighlightedProfiles(
  limit = HIGHLIGHTED_PROFILE_COUNT,
): Promise<HighlightedProfilesResult> {
  return { profiles: demoAllowed ? demoProfiles.slice(0, limit) : [], source: "demo" };
}
