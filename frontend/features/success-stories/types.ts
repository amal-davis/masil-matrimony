import type { StaticImageData } from "next/image";

/**
 * A success story card, from GET /success-stories/ (backend/apps/website_content).
 * Only stories staff published with the couple's consent ever reach this type;
 * that filtering is the backend's job, not the UI's.
 */
export interface SuccessStory {
  /** Stable key for the card. */
  id: string;
  /** The story's address: /success-stories/<slug>. */
  slug: string;
  /** Short title, e.g. "A Beautiful Beginning". */
  heading: string;
  /**
   * The couple's names exactly as they agreed to have them shown, e.g. "Anu & Rahul".
   * Optional: when missing, cards lead with the heading instead. Never invent names.
   */
  couple?: string;
  /** The short description for the card. The full story is only on the story's own page. */
  summary: string;
  /** Couple photo, or null to show the illustrated placeholder. */
  photo: {
    src: string | StaticImageData;
    alt: string;
    width?: number;
    height?: number;
    /** CSS object-position for the 4:3 card crop, e.g. "60% 30%". Defaults to centre. */
    position?: string;
  } | null;
  publishedAt?: string;
}

/** A story's own page: the card plus the full text, as plain-text paragraphs. */
export interface SuccessStoryDetail extends SuccessStory {
  paragraphs: string[];
}

export type SuccessStoriesResult = {
  stories: SuccessStory[];
  /** All published stories (across pages). */
  count: number;
  hasNext: boolean;
  hasPrevious: boolean;
  /** "demo" means fictional sample content, which the UI must label as such. */
  source: "api" | "demo";
};
