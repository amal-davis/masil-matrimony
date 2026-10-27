/**
 * Option lists for the partner search filters.
 *
 * PROVISIONAL: the backend has no profile models or lookup endpoints yet
 * (docs/database-design.md plans Profile.religion, caste, location,
 * marital_status, mother_tongue and height). Until those exist these lists are
 * the single source for the UI. When lookup data is served by the API, load it
 * here and keep the `value`s in sync with what the search endpoint accepts.
 */

export type Option<T extends string = string> = { value: T; label: string };

export const lookingForOptions = [
  { value: "bride", label: "Bride" },
  { value: "groom", label: "Groom" },
] as const satisfies readonly Option[];

/** The age slider's scale, in whole years. The API accepts 18-80; the top of the scale means "no maximum". */
export const AGE_RANGE = { min: 18, max: 70 } as const;

/**
 * The height slider's scale in centimetres (4′6″ to 6′6″), the unit the API
 * filters on (Profile.height_cm). Either end of the scale means "no limit".
 */
export const HEIGHT_RANGE_CM = { min: 137, max: 198 } as const;

/** 4′6″ to 6′6″ in one-inch steps; values are centimetres. Used by the profile editor. */

export const heightOptions: Option[] = Array.from({ length: 6 * 12 + 6 - (4 * 12 + 6) + 1 }, (_, i) => {
  const inches = 4 * 12 + 6 + i;
  return { value: String(Math.round(inches * 2.54)), label: `${Math.floor(inches / 12)}′${inches % 12}″` };
});

export const religionOptions = [
  { value: "hindu", label: "Hindu" },
  { value: "christian", label: "Christian" },
  { value: "muslim", label: "Muslim" },
  { value: "other", label: "Other" },
] as const satisfies readonly Option[];

export type Religion = (typeof religionOptions)[number]["value"];

/** Communities offered for each religion. A religion with none disables the field. */
export const communityOptions: Record<Religion, Option[]> = {
  hindu: [
    { value: "nair", label: "Nair" },
    { value: "ezhava", label: "Ezhava" },
    { value: "thiyya", label: "Thiyya" },
    { value: "namboothiri", label: "Namboothiri" },
    { value: "viswakarma", label: "Viswakarma" },
    { value: "nadar", label: "Nadar" },
    { value: "dheevara", label: "Dheevara" },
    { value: "hindu-other", label: "Other Hindu community" },
  ],
  christian: [
    { value: "syro-malabar", label: "Syro-Malabar Catholic" },
    { value: "latin-catholic", label: "Latin Catholic" },
    { value: "syro-malankara", label: "Syro-Malankara Catholic" },
    { value: "malankara-orthodox", label: "Malankara Orthodox" },
    { value: "jacobite", label: "Jacobite" },
    { value: "marthoma", label: "Marthoma" },
    { value: "csi", label: "CSI" },
    { value: "pentecostal", label: "Pentecostal" },
    { value: "christian-other", label: "Other Christian denomination" },
  ],
  muslim: [
    { value: "sunni", label: "Sunni" },
    { value: "mujahid", label: "Mujahid" },
    { value: "muslim-other", label: "Other Muslim community" },
  ],
  other: [],
};

export function communitiesFor(religion: string): Option[] {
  return communityOptions[religion as Religion] ?? [];
}

export const locationGroups: { label: string; options: Option[] }[] = [
  {
    label: "Kerala",
    options: [
      "Thiruvananthapuram",
      "Kollam",
      "Pathanamthitta",
      "Alappuzha",
      "Kottayam",
      "Idukki",
      "Ernakulam",
      "Thrissur",
      "Palakkad",
      "Malappuram",
      "Kozhikode",
      "Wayanad",
      "Kannur",
      "Kasaragod",
    ].map((district) => ({ value: district.toLowerCase(), label: district })),
  },
  {
    label: "Outside Kerala",
    options: [
      { value: "rest-of-india", label: "Elsewhere in India" },
      { value: "abroad", label: "Outside India" },
    ],
  },
];

export const locationOptions: Option[] = locationGroups.flatMap((group) => group.options);

export const maritalStatusOptions = [
  { value: "never_married", label: "Never married" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
  { value: "awaiting_divorce", label: "Awaiting divorce" },
] as const satisfies readonly Option[];

export const motherTongueOptions = [
  { value: "malayalam", label: "Malayalam" },
  { value: "tamil", label: "Tamil" },
  { value: "kannada", label: "Kannada" },
  { value: "tulu", label: "Tulu" },
  { value: "konkani", label: "Konkani" },
  { value: "telugu", label: "Telugu" },
  { value: "hindi", label: "Hindi" },
  { value: "other", label: "Other" },
] as const satisfies readonly Option[];
