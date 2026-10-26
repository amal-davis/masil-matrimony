import { demoProfileDetails } from "@/features/profiles/demo-profiles";

import type { HighlightedProfile } from "./types";

/**
 * TEMPORARY, FICTIONAL demonstration cards, derived from the demo profile
 * details (features/profiles/demo-profiles.ts) so a card and the profile page
 * it opens always show the same person. These are not real people and have no
 * photos on purpose: the card shows an illustrated avatar instead.
 *
 * Used only by the static design preview, which has no API (see api.ts). Real
 * visitors always get GET /profiles/highlighted/.
 */
export const demoProfiles: HighlightedProfile[] = demoProfileDetails.map(
  ({ id, profileCode, displayName, gender, age, education, location, photos, isVerified }) => ({
    id,
    profileCode,
    displayName,
    gender,
    age,
    education,
    location: { city: location.city, district: location.district, state: location.state },
    photo: photos[0] ?? null,
    isVerified,
  }),
);
