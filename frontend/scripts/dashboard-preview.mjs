/**
 * Builds or serves the member dashboard as a UI PREVIEW: no login, fictional
 * sample data (features/dashboard/preview.ts), nothing sent to the API. For
 * showing the design to a client; never deploy it as the live site.
 *
 *   npm run preview:build   build into .next-preview (the normal .next build is untouched)
 *   npm run preview:start   serve it at http://localhost:3001/dashboard
 */
import { spawnSync } from "node:child_process";

const command = process.argv[2];
if (command !== "build" && command !== "start") {
  console.error("Usage: node scripts/dashboard-preview.mjs build|start");
  process.exit(1);
}

const env = {
  ...process.env,
  NEXT_PUBLIC_DASHBOARD_PREVIEW: "true",
  // The sample members are the site's demo profiles; their pages must exist too.
  NEXT_PUBLIC_SHOW_DEMO_PROFILES: "true",
  NEXT_DIST_DIR: ".next-preview",
};
const args = command === "build" ? ["next", "build"] : ["next", "start", "-p", process.env.PORT ?? "3001"];
const result = spawnSync("npx", args, { stdio: "inherit", env, shell: process.platform === "win32" });
process.exit(result.status ?? 1);
