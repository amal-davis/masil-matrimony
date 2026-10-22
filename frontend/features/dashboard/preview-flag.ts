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

/**
 * True while building the static GitHub Pages preview (output: "export"), where
 * pages can't read the request (query string, time) on the server. Server-side
 * use only: GITHUB_PAGES isn't a NEXT_PUBLIC_ variable.
 */
export const STATIC_EXPORT = process.env.GITHUB_PAGES === "true";

/** Path prefix for plain <img>/<a> URLs (GitHub Pages serves the site under /<repo>). */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
