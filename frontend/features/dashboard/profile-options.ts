import {
  communitiesFor,
  heightOptions,
  maritalStatusOptions,
  motherTongueOptions,
  religionOptions,
  type Option,
} from "@/features/partner-search/options";
import { createdForOptions, genderOptions } from "@/features/registration/schema";

/**
 * Option lists for the profile editor. Values must match the API's choices
 * (backend/apps/profiles/choices.py); the shared ones come from the partner
 * search and registration lists so labels read the same everywhere.
 */

export { communitiesFor, createdForOptions, genderOptions, heightOptions, maritalStatusOptions, motherTongueOptions, religionOptions };
export type { Option };

export const employmentTypeOptions: Option[] = [
  { value: "private", label: "Private sector" },
  { value: "government", label: "Government / public sector" },
  { value: "business", label: "Business" },
  { value: "self_employed", label: "Self-employed / professional" },
  { value: "not_working", label: "Not working" },
  { value: "other", label: "Other" },
];

export const annualIncomeOptions: Option[] = [
  { value: "under_3l", label: "Below ₹3 lakh" },
  { value: "3l_5l", label: "₹3–5 lakh" },
  { value: "5l_10l", label: "₹5–10 lakh" },
  { value: "10l_20l", label: "₹10–20 lakh" },
  { value: "20l_50l", label: "₹20–50 lakh" },
  { value: "over_50l", label: "Above ₹50 lakh" },
];

export const familyTypeOptions: Option[] = [
  { value: "nuclear", label: "Nuclear family" },
  { value: "joint", label: "Joint family" },
  { value: "other", label: "Other" },
];

export const familyValuesOptions: Option[] = [
  { value: "traditional", label: "Traditional" },
  { value: "moderate", label: "Moderate" },
  { value: "liberal", label: "Liberal" },
];

export const dietOptions: Option[] = [
  { value: "vegetarian", label: "Vegetarian" },
  { value: "eggetarian", label: "Eggetarian" },
  { value: "non_vegetarian", label: "Non-vegetarian" },
];

export const visibilityOptions: Option[] = [
  { value: "members", label: "Visible to members" },
  { value: "hidden", label: "Hidden from everyone" },
];

export const photoVisibilityOptions: Option[] = [
  { value: "members", label: "All members" },
  { value: "accepted", label: "Only members whose interest I've accepted" },
];

export const contactSharingOptions: Option[] = [
  { value: "hidden", label: "Don't share my mobile number" },
  { value: "paid_members", label: "Members whose package includes contact access" },
];

/** Minimum legal age of marriage in India, as enforced by the API. */
export const MIN_AGE = { female: 18, male: 21 } as const;

export const ageOptions: Option[] = Array.from({ length: 80 - 18 + 1 }, (_, i) => ({
  value: String(18 + i),
  label: String(18 + i),
}));

export function optionLabel(options: readonly Option[], value: string | null | undefined): string {
  return options.find((option) => option.value === value)?.label ?? "";
}
