import { connection } from "next/server";

import { DASHBOARD_PREVIEW, STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { api } from "@/lib/api/client";

import { toPackage, type MembershipPackage, type PackageDto } from "./packages";

export type PackagesResult = { ok: true; packages: MembershipPackage[] } | { ok: false };

/**
 * The packages on offer, in display order, from GET /memberships/packages/.
 *
 * Fetched on every request (no cache), so a fee or availability change made in
 * the admin shows at once; callers render inside a <Suspense> boundary. When
 * the API can't be reached the page says so rather than showing old prices.
 *
 * UI preview builds never call the API (features/dashboard/preview-flag.ts), so
 * they show preview-packages.json: a snapshot of this endpoint that a backend
 * test (apps/memberships/tests.py) checks against the real response.
 */
export async function getPackages(): Promise<PackagesResult> {
  if (DASHBOARD_PREVIEW) {
    const { default: snapshot } = await import("./preview-packages.json");
    return { ok: true, packages: (snapshot as PackageDto[]).map(toPackage) };
  }
  if (!STATIC_EXPORT) await connection();
  try {
    const data = await api.get<PackageDto[]>("/memberships/packages/", { cache: "no-store" });
    return { ok: true, packages: data.map(toPackage) };
  } catch (error) {
    console.error("Couldn't load membership packages", error);
    return { ok: false };
  }
}
