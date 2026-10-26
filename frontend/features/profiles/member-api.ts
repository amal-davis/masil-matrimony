import { accessToken } from "@/features/auth/session";
import type { MemberProfileDetail, ProfileAccess } from "@/features/dashboard/types";
import { api, ApiError } from "@/lib/api/client";

import { normaliseProfileCode } from "./api";
import type { ProfileDetail } from "./types";

export type MemberProfileResult =
  | { kind: "found"; profile: ProfileDetail; viewer: MemberProfileDetail["viewer"]; access: ProfileAccess }
  /** Not signed in, and this member hasn't agreed to be shown publicly (or the code is unknown). */
  | { kind: "signed_out" }
  /** Signed in, but the member hasn't created their own profile yet. */
  | { kind: "no_profile" }
  | { kind: "not_found" };

const orUndefined = (value: string | null | undefined) => (value ? value : undefined);
const listOrUndefined = (values: string[]) => (values.length ? values : undefined);

/**
 * Map the API's privacy-filtered profile onto the shape the profile page renders.
 * Sections the API didn't send (below full access) stay undefined, not empty.
 */
function toProfileDetail(data: MemberProfileDetail): ProfileDetail {
  const { career, family, lifestyle, partner_preferences: prefs } = data;
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
    career: career && {
      qualification: orUndefined(career.qualification),
      institution: orUndefined(career.institution),
      profession: orUndefined(career.profession),
      employmentType: orUndefined(career.employment_type),
      workLocation: orUndefined(career.work_location),
      annualIncome: orUndefined(career.annual_income),
    },
    family: family && {
      type: orUndefined(family.type),
      values: orUndefined(family.values),
      location: orUndefined(family.location),
      fatherOccupation: orUndefined(family.father_occupation),
      motherOccupation: orUndefined(family.mother_occupation),
      siblings: orUndefined(family.siblings),
    },
    lifestyle: lifestyle && {
      diet: orUndefined(lifestyle.diet),
      hobbies: listOrUndefined(lifestyle.hobbies),
      interests: listOrUndefined(lifestyle.interests),
      languages: listOrUndefined(lifestyle.languages),
    },
    partnerPreferences: prefs && {
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
 * A real member's profile as the API allows this request to see it: fetched with
 * the session's token when there is one (never cached, since the answer differs
 * per viewer), and without one for visitors, whom the API shows only what members
 * agreed to make public. Reads the session cookie, so call it inside <Suspense>.
 */
export async function getMemberProfile(code: string): Promise<MemberProfileResult> {
  const token = await accessToken();
  try {
    const data = await api.get<MemberProfileDetail>(`/profiles/${encodeURIComponent(normaliseProfileCode(code))}/`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    return { kind: "found", profile: toProfileDetail(data), viewer: data.viewer, access: data.access };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) return { kind: "signed_out" };
      if (error.status === 403 && error.body?.code === "no_profile") return { kind: "no_profile" };
      if (error.status === 404) return { kind: "not_found" };
    }
    throw error;
  }
}
