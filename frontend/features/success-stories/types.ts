import type { StaticImageData } from "next/image";

/**
 * Public card data for a success story (testimonial).
 *
 * Shaped after the planned SuccessStory model in docs/database-design.md
 * (website_content app). Only stories the couple consented to share and a
 * content manager published may ever reach this type; that filtering belongs
 * to the backend, not the UI.
 */
export interface SuccessStory {
  /** Stable key for the card. */
  id: string;
  /**
   * The couple's names exactly as they agreed to have them shown, e.g. "Anu & Rahul".
   * Optional: when missing, cards lead with the heading instead. Never invent names
   * for a photo; the demo stories deliberately have none.
   */
  couple?: string;
  /** Short title, e.g. "A Beautiful Beginning". */
  heading: string;
  /** The couple's own words. */
  message: string;
  /** Couple photo, or null to show the illustrated placeholder. */
  photo: {
    src: string | StaticImageData;
    alt: string;
    /** CSS object-position for the 4:3 card crop, e.g. "60% 30%". Defaults to centre. */
    position?: string;
  } | null;
}

export type SuccessStoriesResult = {
  stories: SuccessStory[];
  /** "demo" means fictional sample content, which the UI must label as such. */
  source: "api" | "demo";
};
