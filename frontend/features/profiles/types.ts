/**
 * A member's public profile, as shown on /profile/[id].
 *
 * Shaped after the planned Profile models in docs/database-design.md. Only
 * fields that are safe to show other members belong here: no surname, contact
 * details, exact date of birth, home address, employer name or income unless
 * the API explicitly provides them for display. Every optional field is
 * omitted from the page when it is missing; nothing is filled in by guesswork.
 */
export interface ProfilePhoto {
  url: string;
  width: number;
  height: number;
}

export interface ProfileDetail {
  /** Profile.public_id (UUID); stable key. */
  id: string;
  /** Human-friendly code used in the URL, e.g. "MM100234". */
  profileCode: string;
  /** First name or the display name the member chose to make public. */
  displayName: string;
  gender: "male" | "female";
  age: number;
  heightCm?: number;
  maritalStatus?: string;
  religion?: string;
  community?: string;
  motherTongue?: string;
  nativePlace?: string;
  location: { city?: string; district?: string; state: string; country?: string };
  /** Highest qualification, e.g. "M.Sc." */
  education: string;
  profession?: string;
  /** Set only from the API's verification status; never assumed. */
  isVerified?: boolean;

  /** Public photos, primary first. Empty when there are none or they are hidden. */
  photos: ProfilePhoto[];
  /** The member has photos but chose to show them only to accepted interests. */
  photosHidden?: boolean;

  about?: string;

  career?: {
    qualification?: string;
    institution?: string;
    profession?: string;
    employmentType?: string;
    workLocation?: string;
    /** Only present when the member chose to show it. */
    annualIncome?: string;
  };

  family?: {
    type?: string;
    values?: string;
    location?: string;
    fatherOccupation?: string;
    motherOccupation?: string;
    siblings?: string;
  };

  lifestyle?: {
    diet?: string;
    hobbies?: string[];
    interests?: string[];
    languages?: string[];
  };

  partnerPreferences?: {
    ageRange?: [number, number];
    heightRangeCm?: [number, number];
    maritalStatus?: string;
    religion?: string;
    education?: string;
    location?: string;
    notes?: string;
  };
}

export type ProfileResult = {
  profile: ProfileDetail;
  /** "demo" means fictional sample data, which the UI must label as such. */
  source: "api" | "demo";
};
