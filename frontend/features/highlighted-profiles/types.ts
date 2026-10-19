/**
 * Public card data for a highlighted profile.
 *
 * Shaped after the planned Profile / ProfilePhoto models in
 * docs/database-design.md. Only fields that are safe on a public page belong
 * here: no surname, contact details, exact date of birth or non-public photos.
 */
export interface HighlightedProfile {
  /** Profile.public_id (UUID); stable key for the card. */
  id: string;
  /** Human-friendly code, e.g. "MM100234". */
  profileCode: string;
  /** First name or the display name the member chose to make public. */
  displayName: string;
  /** Profile.gender; picks the illustrated avatar when there is no public photo. */
  gender?: "male" | "female";
  age: number;
  /** Highest qualification, e.g. "M.Sc." */
  education: string;
  location: { city?: string; district?: string; state: string };
  /** Primary photo, only when its visibility is `public`; otherwise null. */
  photo: { url: string; width: number; height: number } | null;
  /** Set only from the API's verification status; never assumed. */
  isVerified?: boolean;
}

export type HighlightedProfilesResult = {
  profiles: HighlightedProfile[];
  /** "demo" means fictional sample data, which the UI must label as such. */
  source: "api" | "demo";
};
