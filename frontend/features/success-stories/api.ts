import { DASHBOARD_PREVIEW, STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { api, ApiError } from "@/lib/api/client";

import { demoStories } from "./demo-stories";
import type { SuccessStoriesResult, SuccessStory, SuccessStoryDetail } from "./types";

/** GET /success-stories/ card (backend/apps/website_content/views.py). */
interface StoryCardDto {
  id: string;
  slug: string;
  title: string;
  couple_names: string;
  summary: string;
  image: { url: string; width: number | null; height: number | null; alt: string } | null;
  published_at: string;
}

interface StoryPageDto {
  count: number;
  next: string | null;
  previous: string | null;
  results: StoryCardDto[];
}

function toStory(dto: StoryCardDto): SuccessStory {
  return {
    id: dto.id,
    slug: dto.slug,
    heading: dto.title,
    couple: dto.couple_names || undefined,
    summary: dto.summary,
    photo: dto.image
      ? { src: dto.image.url, alt: dto.image.alt, width: dto.image.width ?? undefined, height: dto.image.height ?? undefined }
      : null,
    publishedAt: dto.published_at,
  };
}

/** The static design preview has no API, so it shows the labelled sample stories instead. */
const usesSamples = () => STATIC_EXPORT || DASHBOARD_PREVIEW;

/**
 * Published success stories, best first, 20 per page. Read from the API on every
 * request (no caching), so publishing or unpublishing in the admin shows on the
 * next page load. Throws when the API can't be reached: the caller shows an error,
 * never made-up stories.
 */
export async function getSuccessStories(page = 1): Promise<SuccessStoriesResult> {
  if (usesSamples()) {
    return { stories: demoStories, count: demoStories.length, hasNext: false, hasPrevious: false, source: "demo" };
  }
  try {
    const data = await api.get<StoryPageDto>(`/success-stories/${page > 1 ? `?page=${page}` : ""}`, { cache: "no-store" });
    return {
      stories: data.results.map(toStory),
      count: data.count,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
      source: "api",
    };
  } catch (error) {
    // A page past the end is a 404 from the paginator: simply no stories there.
    if (error instanceof ApiError && error.status === 404 && page > 1) {
      return { stories: [], count: 0, hasNext: false, hasPrevious: true, source: "api" };
    }
    throw error;
  }
}

/** One published story by its slug, or null when there's no such published story. Throws if the API fails. */
export async function getSuccessStory(slug: string): Promise<{ story: SuccessStoryDetail; source: "api" | "demo" } | null> {
  if (usesSamples()) {
    const story = demoStories.find((item) => item.slug === slug);
    return story ? { story: { ...story, paragraphs: story.paragraphs }, source: "demo" } : null;
  }
  if (!/^[a-z0-9-]{1,140}$/.test(slug)) return null;
  try {
    const data = await api.get<StoryCardDto & { paragraphs: string[] }>(`/success-stories/${slug}/`, { cache: "no-store" });
    return { story: { ...toStory(data), paragraphs: data.paragraphs }, source: "api" };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Story slugs to prerender at build time: only the samples (real stories render on request). */
export function getPrerenderedStorySlugs(): string[] {
  return usesSamples() ? demoStories.map((story) => story.slug) : [];
}
