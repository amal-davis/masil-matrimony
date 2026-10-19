import { demoStories } from "./demo-stories";
import type { SuccessStoriesResult } from "./types";

/**
 * Demo stories are fictional, so they must never reach real visitors by
 * accident: they show in development, or in a production build only when
 * NEXT_PUBLIC_SHOW_DEMO_STORIES=true is set deliberately (e.g. a staging demo).
 */
const demoAllowed =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_SHOW_DEMO_STORIES === "true";

/**
 * Stories for the homepage "Success Stories" slider.
 *
 * NOT CONNECTED: the backend has no SuccessStory model or API yet
 * (backend/apps/website_content is a placeholder). When it exists, replace the
 * body with a call through the shared client, e.g.
 *
 *   const data = await api.get<SuccessStoryDto[]>("/success-stories/?featured=true");
 *   return { stories: data.map(toSuccessStory), source: "api" };
 *
 * Expected response (planned, not implemented): published stories the couple
 * consented to share, already filtered by the backend:
 *
 *   [{ "id": "uuid", "heading": "…", "message": "…",
 *      "photo": { "url": "https://…", "alt": "…" } | null }]
 *
 * Remote photo hosts then need adding to `images.remotePatterns` in next.config.ts.
 */
export async function getSuccessStories(): Promise<SuccessStoriesResult> {
  return { stories: demoAllowed ? demoStories : [], source: "demo" };
}
