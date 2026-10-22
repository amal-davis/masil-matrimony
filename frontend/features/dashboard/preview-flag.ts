/**
 * UI PREVIEW MODE switch (sample data in ./preview.ts). Kept separate so the
 * proxy and client components can check it without bundling the sample data.
 *
 * Turned on only by building with NEXT_PUBLIC_DASHBOARD_PREVIEW=true
 * (scripts/dashboard-preview.mjs). The dashboard then needs no login and never
 * calls the API. Never enable it on the live site.
 */
export const DASHBOARD_PREVIEW = process.env.NEXT_PUBLIC_DASHBOARD_PREVIEW === "true";

export const PREVIEW_ACTION_MESSAGE = "Preview only: this is sample data, so nothing was saved.";
