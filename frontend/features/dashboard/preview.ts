import { demoProfileDetails } from "@/features/profiles/demo-profiles";
import type { ProfileDetail } from "@/features/profiles/types";

import { BASE_PATH } from "./preview-flag";
import {
  communitiesFor,
  familyTypeOptions,
  familyValuesOptions,
  maritalStatusOptions,
  motherTongueOptions,
  optionLabel,
  religionOptions,
} from "./profile-options";

import type {
  DashboardSummary,
  InterestItem,
  InterestStatus,
  MatchCard,
  MatchInfo,
  MemberCard,
  MembershipInfo,
  NotificationItem,
  OwnPhoto,
  OwnProfile,
  Paginated,
  ShellData,
  ShortlistItem,
} from "./types";

/**
 * FICTIONAL sample data for the dashboard's UI preview mode (switch in
 * ./preview-flag.ts), for showing the design to people without an account,
 * e.g. a client review. In preview mode every page shows this data, every
 * action answers "preview only", and the API is never called, so real member
 * data can't appear.
 */

const at = (date: string) => `${date}T09:30:00+05:30`;

// --- The fictional member using the dashboard ------------------------------

export const previewProfile: OwnProfile = {
  profile_code: "MAS100245",
  status: "active",
  review_note: "",
  submitted_at: at("2026-08-02"),
  identity_locked: true,
  max_photos: 10,
  completion: { percent: 95, missing: ["Employment type"] },
  missing_for_review: [],
  created_for: "self",
  display_name: "Arun",
  gender: "male",
  date_of_birth: "1998-05-14",
  height_cm: 175,
  marital_status: "never_married",
  religion: "hindu",
  community: "nair",
  mother_tongue: "malayalam",
  country: "India",
  state: "Kerala",
  district: "Ernakulam",
  city: "Kochi",
  native_place: "Thrissur",
  about:
    "I'm a software engineer in Kochi who enjoys cricket at the weekend, photography and long drives. I value honesty, kindness and a sense of humour, and I'm close to my family. I'm looking for a caring, independent partner to build a warm home with.",
  highest_education: "B.Tech",
  education_detail: "B.Tech Computer Science",
  institution: "",
  occupation: "Software Engineer",
  employment_type: "",
  work_location: "Kochi",
  annual_income: "",
  income_visible: false,
  family_type: "nuclear",
  family_values: "moderate",
  family_location: "Thrissur",
  father_occupation: "Retired teacher",
  mother_occupation: "Homemaker",
  siblings: "One younger sister, studying",
  diet: "",
  hobbies: ["Cricket", "Photography", "Travel"],
  interests: [],
  languages: ["Malayalam", "English", "Hindi"],
  visibility: "members",
  photo_visibility: "members",
  contact_sharing: "hidden",
  homepage_consent: false,
  partner_preference: {
    age_min: 23,
    age_max: 28,
    height_min_cm: 152,
    height_max_cm: 170,
    marital_statuses: ["never_married"],
    religions: ["hindu"],
    communities: [],
    mother_tongues: [],
    diets: [],
    locations: "Kerala",
    education: "Graduate or above",
    occupation: "",
    notes: "",
    must_haves: ["age", "height", "marital_status", "religion"],
  },
};

/** Illustrated placeholders (public/images/preview), not photographs of anyone. */
export const previewPhotos: OwnPhoto[] = [
  { id: "00000000-0000-4000-8000-000000000001", url: `${BASE_PATH}/images/preview/sample-photo-1.svg`, width: 800, height: 1000, is_primary: true, status: "approved", review_note: "", created_at: at("2026-08-02") },
  { id: "00000000-0000-4000-8000-000000000002", url: `${BASE_PATH}/images/preview/sample-photo-2.svg`, width: 800, height: 1000, is_primary: false, status: "approved", review_note: "", created_at: at("2026-08-05") },
  { id: "00000000-0000-4000-8000-000000000003", url: `${BASE_PATH}/images/preview/sample-photo-3.svg`, width: 800, height: 1000, is_primary: false, status: "pending", review_note: "", created_at: at("2026-10-20") },
];

// --- Other (fictional) members: the site's demo profiles ------------------

function toCard(profile: ProfileDetail): MemberCard {
  return {
    profile_code: profile.profileCode,
    display_name: profile.displayName,
    gender: profile.gender,
    age: profile.age,
    height_cm: profile.heightCm ?? null,
    marital_status: profile.maritalStatus ?? "",
    religion: profile.religion ?? "",
    community: profile.community ?? "",
    education: profile.education,
    occupation: profile.profession ?? "",
    location: {
      city: profile.location.city ?? "",
      district: profile.location.district ?? "",
      state: profile.location.state,
      country: profile.location.country ?? "",
    },
    photo: null,
    photos_hidden: false,
  };
}

const member = (code: string) => toCard(demoProfileDetails.find((profile) => profile.profileCode === code)!);

function interest(n: number, code: string, status: InterestStatus, created: string, responded?: string): InterestItem {
  return {
    id: `00000000-0000-4000-9000-${String(n).padStart(12, "0")}`,
    status,
    created_at: at(created),
    responded_at: responded ? at(responded) : null,
    profile: { ...member(code), available: true },
  };
}

export const previewReceived: InterestItem[] = [
  interest(1, "DEMO001", "pending", "2026-10-21"),
  interest(2, "DEMO003", "pending", "2026-10-19"),
  interest(3, "DEMO005", "accepted", "2026-10-12", "2026-10-13"),
  interest(4, "DEMO007", "declined", "2026-10-02", "2026-10-04"),
];

export const previewSent: InterestItem[] = [
  interest(5, "DEMO009", "pending", "2026-10-20"),
  interest(6, "DEMO011", "accepted", "2026-10-08", "2026-10-10"),
  interest(7, "DEMO003", "withdrawn", "2026-09-28", "2026-09-30"),
];

const SHORTLISTED = ["DEMO003", "DEMO009"];

/**
 * The sample member's matches, scored against their sample preferences (age 23-28, Hindu,
 * Kerala) with the API's weights for those three criteria, so the preview shows real reasons.
 */
function previewMatch(card: MemberCard): MatchInfo {
  const checks: [boolean, number, string][] = [
    [card.age >= 23 && card.age <= 28, 20, "Matches your age preference (23–28)"],
    [card.religion === "Hindu", 15, "Matches your religion preference"],
    [card.location.state.toLowerCase() === "kerala", 12, "Lives in or comes from a place you prefer"],
  ];
  const earned = checks.filter(([ok]) => ok).reduce((sum, [, weight]) => sum + weight, 0);
  return {
    score: Math.round((100 * earned) / 47),
    reasons: checks.filter(([ok]) => ok).map(([, , reason]) => reason),
    not_stated: [],
    mutual: true,
  };
}

export const previewMatches: MatchCard[] = demoProfileDetails
  .filter((profile) => profile.gender === "female")
  .map((profile) => {
    const card = toCard(profile);
    return { ...card, shortlisted: SHORTLISTED.includes(profile.profileCode), match: previewMatch(card) };
  })
  .sort((a, b) => (b.match.score ?? 0) - (a.match.score ?? 0));

export const previewShortlist: ShortlistItem[] = SHORTLISTED.map((code, i) => ({
  created_at: at(`2026-10-1${i + 4}`),
  profile: { ...member(code), available: true },
}));

export const previewMembership: MembershipInfo = {
  current: {
    id: "00000000-0000-4000-a000-000000000001",
    plan_code: "diamond",
    plan_name: "Diamond Membership",
    status: "active",
    starts_at: at("2026-08-01"),
    ends_at: at("2027-08-01"),
    validity_months: 12,
    package_fee: null,
    contact_view_limit: 100,
    contact_views_used: 12,
  },
  history: [],
  entitlements: { package_code: "diamond", outgoing_interest_limit: null, outgoing_interests_used: null, contact_view_limit: 100 },
  online_payment_available: false,
};
previewMembership.history = [previewMembership.current!];

export const previewNotifications: NotificationItem[] = [
  { id: "00000000-0000-4000-b000-000000000001", kind: "interest_received", title: "You've received a new interest", body: "Anjali (DEMO001) is interested in your profile.", link: "/dashboard/interests/received", created_at: at("2026-10-21"), read: false },
  { id: "00000000-0000-4000-b000-000000000002", kind: "interest_received", title: "You've received a new interest", body: "Meera (DEMO003) is interested in your profile.", link: "/dashboard/interests/received", created_at: at("2026-10-19"), read: false },
  { id: "00000000-0000-4000-b000-000000000003", kind: "interest_accepted", title: "Your interest was accepted", body: "Diya (DEMO011) accepted your interest.", link: "/dashboard/interests/sent", created_at: at("2026-10-10"), read: true },
  { id: "00000000-0000-4000-b000-000000000004", kind: "photo_approved", title: "Your photo has been approved", body: "Members can now see this photo, subject to your privacy settings.", link: "/dashboard/photos", created_at: at("2026-08-06"), read: true },
  { id: "00000000-0000-4000-b000-000000000005", kind: "membership_activated", title: "Your Diamond Membership is active", body: "Valid until 01 Aug 2027.", link: "/dashboard/membership", created_at: at("2026-08-01"), read: true },
];

export const previewAccount = {
  id: "00000000-0000-4000-c000-000000000001",
  email: "arun@example.com",
  phone_number: "+919876543210",
  first_name: "Arun",
  last_name: "",
  phone_verified_at: at("2026-07-15"),
  date_joined: at("2026-07-15"),
};

/** The sample member's own profile page (/profile/MAS100245), as other members would see it. */
export function previewProfileDetail(): ProfileDetail {
  const p = previewProfile;
  const pref = p.partner_preference;
  return {
    id: p.profile_code,
    profileCode: p.profile_code,
    displayName: p.display_name,
    gender: p.gender,
    age: 28,
    heightCm: p.height_cm ?? undefined,
    maritalStatus: optionLabel(maritalStatusOptions, p.marital_status),
    religion: optionLabel(religionOptions, p.religion),
    community: optionLabel(communitiesFor(p.religion), p.community),
    motherTongue: optionLabel(motherTongueOptions, p.mother_tongue),
    nativePlace: p.native_place,
    location: { city: p.city, district: p.district, state: p.state, country: p.country },
    education: p.highest_education,
    profession: p.occupation,
    photos: previewPhotos.filter((photo) => photo.status === "approved"),
    about: p.about,
    career: {
      qualification: p.education_detail,
      profession: p.occupation,
      workLocation: p.work_location,
    },
    family: {
      type: optionLabel(familyTypeOptions, p.family_type),
      values: optionLabel(familyValuesOptions, p.family_values),
      location: p.family_location,
      fatherOccupation: p.father_occupation,
      motherOccupation: p.mother_occupation,
      siblings: p.siblings,
    },
    lifestyle: { hobbies: p.hobbies, languages: p.languages },
    partnerPreferences: {
      ageRange: [pref.age_min!, pref.age_max!],
      heightRangeCm: [pref.height_min_cm!, pref.height_max_cm!],
      maritalStatus: "Never married",
      religion: "Hindu",
      education: pref.education,
      location: pref.locations,
    },
  };
}

/** The overview, with every count computed from the sample lists above. */
export function previewSummary(): DashboardSummary {
  const live = (items: InterestItem[]) => items.filter((item) => item.status !== "withdrawn");
  const received = live(previewReceived);
  const sent = live(previewSent);
  return {
    member: { first_name: "Arun", phone_verified: true },
    membership: previewMembership.current,
    notifications: {
      unread: previewNotifications.filter((item) => !item.read).length,
      recent: previewNotifications.slice(0, 5),
    },
    profile: {
      profile_code: previewProfile.profile_code,
      display_name: previewProfile.display_name,
      status: previewProfile.status,
      review_note: "",
      completion: previewProfile.completion,
      missing_for_review: [],
      photo: { url: previewPhotos[0].url, status: "approved" },
      photo_count: previewPhotos.length,
    },
    interests: {
      received: received.length,
      awaiting_your_response: received.filter((item) => item.status === "pending").length,
      sent: sent.length,
      sent_pending: sent.filter((item) => item.status === "pending").length,
      accepted: [...received, ...sent].filter((item) => item.status === "accepted").length,
    },
    shortlisted: previewShortlist.length,
    recent_interests: [
      ...received.map((item) => ({ ...item, direction: "received" as const })),
      ...sent.map((item) => ({ ...item, direction: "sent" as const })),
    ]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, 5),
  };
}

/** The frame's live values (avatar, name, badges) for preview builds, from the same sample data. */
export function previewShellData(): ShellData {
  const summary = previewSummary();
  return {
    name: summary.profile!.display_name,
    profileCode: summary.profile!.profile_code,
    photoUrl: summary.profile!.photo?.url ?? null,
    membership: summary.membership?.plan_name ?? null,
    unreadNotifications: summary.notifications.unread,
    awaitingReply: summary.interests!.awaiting_your_response,
  };
}

/** A sample list filtered and paged like the API's. */
export function previewPage<T>(items: T[], page: number, status?: string): Paginated<T> {
  const filtered = status ? items.filter((item) => (item as { status?: string }).status === status) : items;
  const results = filtered.slice((page - 1) * 20, page * 20);
  return { count: filtered.length, next: null, previous: null, results };
}
