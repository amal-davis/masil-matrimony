import type { StaticImageData } from "next/image";

import coupleLotusField from "@/public/images/hero/couple-lotus-field.jpg";
import garlandedCouple from "@/public/images/hero/garlanded-couple.jpg";
import keralaWeddingFamily from "@/public/images/hero/kerala-wedding-family.jpg";

export type HeroSlide = {
  id: string;
  image: StaticImageData;
  alt: string;
  /** CSS object-position for the narrow mobile crop and the wide desktop crop. */
  position: { mobile: string; desktop: string };
  eyebrow?: string;
  heading: string;
  description: string;
  /** Where the image came from. Not rendered; keep it up to date when swapping images. */
  credit: string;
};

/**
 * Homepage hero slides. Edit this list to change copy or images; the slider
 * renders any number of slides. Images live in public/images/hero/.
 */
export const heroSlides: HeroSlide[] = [
  {
    id: "perfect-partner",
    image: coupleLotusField,
    alt: "A smiling Kerala couple in traditional dress among lotus flowers",
    position: { mobile: "58% 20%", desktop: "center 8%" },
    eyebrow: "Trusted matrimony for Kerala families",
    heading: "Find Your Perfect Life Partner",
    description:
      "Begin a meaningful journey toward marriage with a profile that reflects your values, dreams, and family.",
    credit:
      "Picnu (@arununnikrishnan) on Unsplash, https://unsplash.com/photos/IyxLjgxNj3s (Unsplash License)",
  },
  {
    id: "two-families",
    image: keralaWeddingFamily,
    alt: "A bride and groom in Kerala wedding attire surrounded by their families",
    position: { mobile: "30% 20%", desktop: "center 22%" },
    eyebrow: "Verified profiles, personal care",
    heading: "Where Two Families Become One",
    description: "Discover compatible matches and take the next step toward a beautiful future together.",
    credit:
      "shades by 43 (@shades_by_43) on Unsplash, https://unsplash.com/photos/VJP7K4uihUA (Unsplash License)",
  },
  {
    id: "your-story",
    image: garlandedCouple,
    alt: "A newly married couple wearing wedding garlands, smiling at each other",
    position: { mobile: "52% 28%", desktop: "center 32%" },
    eyebrow: "Privacy you control",
    heading: "Your Story. Your Perfect Match.",
    description: "Explore meaningful connections and find someone who shares your hopes for tomorrow.",
    credit:
      "Sabesh Photography LTD (@sabesh) on Unsplash, https://unsplash.com/photos/OzyvCE9a60M (Unsplash License)",
  },
];

/** How long each slide stays before autoplay advances. */
export const HERO_SLIDE_DURATION_MS = 6500;
