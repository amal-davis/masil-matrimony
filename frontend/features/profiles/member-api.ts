import { accessToken } from "@/features/auth/session";
import type { MemberProfileDetail } from "@/features/dashboard/types";
import { api, ApiError } from "@/lib/api/client";

import { normaliseProfileCode } from "./api";
import type { ProfileDetail } from "./types";

export type MemberProfileResult =
  | { kind: "found"; profile: ProfileDetail; viewer: MemberProfileDetail["viewer"] }
  /** Real profiles are for signed-in members only. */
  | { kind: "signed_out" }
  /** Signed in, but the member hasn't created their own profile yet. */
  | { kind: "no_profile" }
  | { kind: "not_found" };

const orUndefined = (value: string | null | undefined) => (value ? value : undefined);
const listOrUndefined = (values: string[]) => (values.length ? values : undefined);

/** Map the API's privacy-filtered profile onto the shape the profile page renders. */
function toProfileDetail(data: MemberProfileDetail): ProfileDetail {
  const prefs = data.partner_preferences;
  return {
    id: data.profile_code,
    profileCode: data.profile_code,
    displayName: data.display_name,
    gender: data.gender,
    age: data.age,
    heightCm: data.height_cm ?? undefined,
    maritalStatus: orUndefined(data.marital_status),
    religion: orUndefined(data.religion),
    community: orUndefined(data.community),
    motherTongue: orUndefined(data.mother_tongue),
    nativePlace: orUndefined(data.native_place),
    location: {
      city: orUndefined(data.location.city),
      district: orUndefined(data.location.district),
      state: data.location.state || data.location.country,
      country: orUndefined(data.location.country),
    },
    education: data.education,
    profession: orUndefined(data.occupation),
    photos: data.photos,
    photosHidden: data.photos_hidden,
    about: orUndefined(data.about),
    career: {
      qualification: orUndefined(data.career.qualification),
      institution: orUndefined(data.career.institution),
      profession: orUndefined(data.career.profession),
      employmentType: orUndefined(data.career.employment_type),
      workLocation: orUndefined(data.career.work_location),
      annualIncome: orUndefined(data.career.annual_income),
    },
    family: {
      type: orUndefined(data.family.type),
      values: orUndefined(data.family.values),
      location: orUndefined(data.family.location),
      fatherOccupation: orUndefined(data.family.father_occupation),
      motherOccupation: orUndefined(data.family.mother_occupation),
      siblings: orUndefined(data.family.siblings),
    },
    lifestyle: {
      diet: orUndefined(data.lifestyle.diet),
      hobbies: listOrUndefined(data.lifestyle.hobbies),
      interests: listOrUndefined(data.lifestyle.interests),
      languages: listOrUndefined(data.lifestyle.languages),
    },
    partnerPreferences: {
      ageRange: prefs.age_range ?? undefined,
      heightRangeCm: prefs.height_range_cm ?? undefined,
      maritalStatus: orUndefined(prefs.marital_status),
      religion: orUndefined(prefs.religion),
      education: orUndefined(prefs.education),
      location: orUndefined(prefs.location),
      notes: orUndefined(prefs.notes),
    },
  };
}

/**
 * A real member's profile, fetched as the signed-in viewer so the API applies
 * their visibility and privacy rules. Reads the session cookie, so call it
 * inside a <Suspense> boundary.
 */
export async function getMemberProfile(code: string): Promise<MemberProfileResult> {
  const token = await accessToken();
  if (!token) return { kind: "signed_out" };
  try {
    const data = await api.get<MemberProfileDetail>(`/profiles/${encodeURIComponent(normaliseProfileCode(code))}/`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    return { kind: "found", profile: toProfileDetail(data), viewer: data.viewer };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) return { kind: "signed_out" };
      if (error.status === 403 && error.body?.code === "no_profile") return { kind: "no_profile" };
      if (error.status === 404) return { kind: "not_found" };
    }
    throw error;
  }
}
