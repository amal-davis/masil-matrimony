import type { NextConfig } from "next";

/**
 * GITHUB_PAGES=true builds a static preview of the public site (`out/`) for
 * GitHub Pages; see .github/workflows/deploy-pages.yml. Normal builds are
 * unaffected. NEXT_PUBLIC_BASE_PATH is the repository path, e.g. "/masil-matrimony".
 */
const githubPages = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  // The dashboard UI preview (scripts/dashboard-preview.mjs) builds into its own
  // folder so it never replaces the normal build.
  ...(process.env.NEXT_DIST_DIR && { distDir: process.env.NEXT_DIST_DIR }),
  env: {
    // Footer copyright year (see components/layout/current-year.tsx).
    NEXT_PUBLIC_BUILD_YEAR: String(new Date().getFullYear()),
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(githubPages && {
    output: "export",
    // A static export can't use partial prerendering, which Cache Components turns on.
    cacheComponents: false,
    partialPrefetching: false,
    basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
    // GitHub Pages serves folders, so /faq/ → faq/index.html.
    trailingSlash: true,
    // There is no image optimisation server on a static host.
    images: { unoptimized: true },
  }),
};

export default nextConfig;
