import { z } from "zod";

import {
  AGE_RANGE,
  communitiesFor,
  heightOptions,
  HEIGHT_RANGE_CM,
  locationOptions,
  lookingForOptions,
  maritalStatusOptions,
  motherTongueOptions,
  religionOptions,
  type Option,
} from "./options";

/** Where a search goes. The search page reads the same query parameters back. */
export const SEARCH_RESULTS_PATH = "/search";

/** "" means "any": every filter except bride/groom is optional. */
const anyOf = (options: readonly Option[], message: string) =>
  z.string().refine((value) => value === "" || options.some((option) => option.value === value), message);

const numberIn = (min: number, max: number, message: string) =>
  z
    .string()
    .refine((value) => value === "" || (/^\d+$/.test(value) && +value >= min && +value <= max), message);

const fields = z.object({
  lookingFor: z.enum(["bride", "groom"], { error: "Choose bride or groom." }),
  ageMin: numberIn(AGE_RANGE.min, AGE_RANGE.max, "Choose a valid age."),
  ageMax: numberIn(AGE_RANGE.min, AGE_RANGE.max, "Choose a valid age."),
  heightMin: numberIn(HEIGHT_RANGE_CM.min, HEIGHT_RANGE_CM.max, "Choose a valid height."),
  heightMax: numberIn(HEIGHT_RANGE_CM.min, HEIGHT_RANGE_CM.max, "Choose a valid height."),
  religion: anyOf(religionOptions, "Choose a religion from the list."),
  community: z.string(),
  location: anyOf(locationOptions, "Choose a location from the list."),
  maritalStatus: anyOf(maritalStatusOptions, "Choose a marital status from the list."),
  motherTongue: anyOf(motherTongueOptions, "Choose a mother tongue from the list."),
});

// Cross-field rules run even while other fields (e.g. bride/groom) are still invalid.
const ranges = fields.pick({ ageMin: true, ageMax: true, heightMin: true, heightMax: true });
const religionAndCommunity = fields.pick({ religion: true, community: true });

export const partnerSearchSchema = fields
  .refine((data) => !data.ageMin || !data.ageMax || +data.ageMin <= +data.ageMax, {
    path: ["ageMax"],
    message: "The maximum age can’t be lower than the minimum.",
    when: (payload) => ranges.safeParse(payload.value).success,
  })
  .refine((data) => !data.heightMin || !data.heightMax || +data.heightMin <= +data.heightMax, {
    path: ["heightMax"],
    message: "The maximum height can’t be lower than the minimum.",
    when: (payload) => ranges.safeParse(payload.value).success,
  })
  .refine(
    (data) => data.community === "" || communitiesFor(data.religion).some((c) => c.value === data.community),
    {
      path: ["community"],
      message: "Choose a community for the selected religion.",
      when: (payload) => religionAndCommunity.safeParse(payload.value).success,
    },
  );

export type PartnerSearchInput = z.input<typeof partnerSearchSchema>;
export type PartnerSearchValues = z.output<typeof partnerSearchSchema>;

export const emptyFilters: Omit<PartnerSearchInput, "lookingFor"> = {
  ageMin: "",
  ageMax: "",
  heightMin: "",
  heightMax: "",
  religion: "",
  community: "",
  location: "",
  maritalStatus: "",
  motherTongue: "",
};

/**
 * URL query parameters, following the planned `GET /profiles/search/` contract
 * in docs/api-specification.md (snake_case, `age_min`/`age_max`, ...).
 * `gender` is the gender of the profiles being searched for.
 */
const queryKeys = {
  ageMin: "age_min",
  ageMax: "age_max",
  heightMin: "height_min",
  heightMax: "height_max",
  religion: "religion",
  community: "caste",
  location: "location",
  maritalStatus: "marital_status",
  motherTongue: "mother_tongue",
} as const satisfies Record<keyof typeof emptyFilters, string>;

const genderFor = { bride: "female", groom: "male" } as const;

export function filtersToQuery(values: PartnerSearchValues): URLSearchParams {
  const params = new URLSearchParams({ gender: genderFor[values.lookingFor] });
  for (const [field, key] of Object.entries(queryKeys)) {
    const value = values[field as keyof typeof queryKeys];
    if (value) params.set(key, value);
  }
  return params;
}

type QueryInput = Record<string, string | string[] | undefined>;

/** Read filters back from the URL, dropping anything invalid or unknown. */
export function filtersFromQuery(query: QueryInput): Partial<PartnerSearchInput> {
  const first = (key: string) => {
    const value = query[key];
    return (Array.isArray(value) ? value[0] : value) ?? "";
  };

  const values: Partial<PartnerSearchInput> = {};
  const gender = first("gender");
  const lookingFor = (Object.keys(genderFor) as (keyof typeof genderFor)[]).find(
    (key) => genderFor[key] === gender,
  );
  if (lookingFor) values.lookingFor = lookingFor;

  for (const [field, key] of Object.entries(queryKeys) as [keyof typeof queryKeys, string][]) {
    const value = first(key);
    if (value && fields.shape[field].safeParse(value).success) values[field] = value;
  }
  if (values.community && !communitiesFor(values.religion ?? "").some((c) => c.value === values.community)) {
    delete values.community;
  }
  return values;
}

/** Human-readable summary of the active filters, e.g. for a results heading. */
export function describeFilters(values: Partial<PartnerSearchInput>): string[] {
  const label = (options: readonly Option[], value?: string) =>
    options.find((option) => option.value === value)?.label;
  const range = (min?: string, max?: string, format: (v: string) => string = (v) => v) =>
    min && max
      ? `${format(min)} – ${format(max)}`
      : min
        ? `from ${format(min)}`
        : max
          ? `up to ${format(max)}`
          : "";
  const height = (cm: string) => label(heightOptions, cm) ?? `${cm} cm`;

  return [
    values.lookingFor && label(lookingForOptions, values.lookingFor),
    range(values.ageMin, values.ageMax) && `Age ${range(values.ageMin, values.ageMax)}`,
    range(values.heightMin, values.heightMax) &&
      `Height ${range(values.heightMin, values.heightMax, height)}`,
    label(religionOptions, values.religion),
    label(communitiesFor(values.religion ?? ""), values.community),
    label(locationOptions, values.location),
    label(maritalStatusOptions, values.maritalStatus),
    values.motherTongue && `${label(motherTongueOptions, values.motherTongue)} speaking`,
  ].filter((item): item is string => Boolean(item));
}
