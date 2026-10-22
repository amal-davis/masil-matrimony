import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";

import { demoProfileDetails } from "./demo-profiles";
import type { ProfileResult } from "./types";

/**
 * Demo profiles are fictional, so they must never reach real visitors by
 * accident: they show in development, or in a production build only when
 * NEXT_PUBLIC_SHOW_DEMO_PROFILES=true is set deliberately (e.g. a staging demo).
 */
export const DEMO_PROFILES_ALLOWED =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_SHOW_DEMO_PROFILES === "true";

/** Profile codes are shown in upper case; accept any case in the URL. */
export const normaliseProfileCode = (code: string) => decodeURIComponent(code).trim().toUpperCase();

/**
 * One member's public profile, or null when there is no such profile.
 *
 * NOT CONNECTED: the backend has no profiles API yet. When it exists, replace
 * the body with a call through the shared client, e.g.
 *
 *   const data = await api.get<ProfileDetailDto>(`/profiles/${encodeURIComponent(code)}/`);
 *   return { profile: toProfileDetail(data), source: "api" };
 *
 * returning null on a 404. The API must apply the member's privacy settings
 * (hidden photos, contact details) before responding; this page only displays
 * what it receives.
 */
export async function getProfile(code: string): Promise<ProfileResult | null> {
  const wanted = normaliseProfileCode(code);
  // Dashboard UI preview builds also show the fictional dashboard member's own profile.
  if (DASHBOARD_PREVIEW && wanted === "MAS100245") {
    const { previewProfileDetail } = await import("@/features/dashboard/preview");
    return { profile: previewProfileDetail(), source: "demo" };
  }
  if (!DEMO_PROFILES_ALLOWED) return null;
  const profile = demoProfileDetails.find((item) => item.profileCode === wanted);
  return profile ? { profile, source: "demo" } : null;
}

/** Profile codes to prerender at build time. Real profiles render on first request instead. */
export async function getPrerenderedProfileCodes(): Promise<string[]> {
  const codes = DEMO_PROFILES_ALLOWED ? demoProfileDetails.map((profile) => profile.profileCode) : [];
  // Dashboard preview builds also need the sample member's own page (e.g. on static hosts).
  return DASHBOARD_PREVIEW ? [...codes, "MAS100245"] : codes;
}
