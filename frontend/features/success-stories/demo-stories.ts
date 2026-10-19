import coupleLotusField from "@/public/images/hero/couple-lotus-field.jpg";
import garlandedCouple from "@/public/images/hero/garlanded-couple.jpg";
import keralaWeddingFamily from "@/public/images/hero/kerala-wedding-family.jpg";

import type { SuccessStory } from "./types";

/**
 * TEMPORARY, FICTIONAL demonstration stories for building the homepage before
 * the success stories API exists. No real couple wrote these words.
 *
 * The photos are the homepage hero's stock images (Unsplash; credits in
 * features/home-hero/slides.ts), reused as placeholders. The people pictured
 * are not Maasil members and did not give these testimonials, so this content
 * must never be shown on the live site: replace it with real stories and
 * photos the couples consented to share.
 *
 * Remove this file once GET /success-stories/ is implemented; see api.ts.
 */

const lotusField = {
  src: coupleLotusField,
  alt: "A smiling couple in traditional dress among lotus flowers",
  position: "62% 35%",
};
const garlanded = {
  src: garlandedCouple,
  alt: "A newly married couple wearing wedding garlands, smiling at each other",
  position: "55% 30%",
};
const weddingFamily = {
  src: keralaWeddingFamily,
  alt: "A bride and groom in Kerala wedding attire surrounded by their families",
  position: "28% 35%",
};
export const demoStories: SuccessStory[] = [
  {
    id: "demo-story-1",
    heading: "A Beautiful Beginning",
    message:
      "We found someone who shared our values and dreams. The experience helped both our families take the next step with confidence.",
    photo: lotusField,
  },
  {
    id: "demo-story-2",
    heading: "Two Families, One Celebration",
    message:
      "Our parents spoke first, and we were grateful for that. By the time we met, it already felt as though our families knew each other well.",
    photo: garlanded,
  },
  {
    id: "demo-story-3",
    heading: "Worth the Wait",
    message:
      "We took our time and never felt rushed. Being able to share details at our own pace made every conversation feel honest.",
    photo: weddingFamily,
  },
  {
    id: "demo-story-4",
    heading: "Across the Miles",
    message:
      "We were working in different cities, yet the search kept our preferences close to home. Distance never felt like a barrier.",
    photo: garlanded,
  },
  {
    id: "demo-story-5",
    heading: "Guided With Care",
    message:
      "Our advisor listened to what mattered to our family and helped us shortlist thoughtfully. We always knew who to call with a question.",
    photo: weddingFamily,
  },
  {
    id: "demo-story-6",
    heading: "A Promise for Tomorrow",
    message:
      "From the first visit to the wedding day, everything felt natural. We are starting our life together with the blessings of both families.",
    photo: lotusField,
  },
];
