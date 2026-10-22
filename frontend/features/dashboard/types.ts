/** Shapes of the member API responses used by the dashboard (backend/apps/*). */

export type ProfileStatus = "draft" | "pending_review" | "active" | "rejected" | "suspended";
export type PhotoStatus = "pending" | "approved" | "rejected";
export type InterestStatus = "pending" | "accepted" | "declined" | "withdrawn";

export interface Completion {
  percent: number;
  missing: string[];
}

export interface PartnerPreference {
  age_min: number | null;
  age_max: number | null;
  height_min_cm: number | null;
  height_max_cm: number | null;
  marital_statuses: string[];
  religions: string[];
  communities: string[];
  locations: string;
  education: string;
  occupation: string;
  notes: string;
}

/** GET /profiles/me/: the member's own profile, raw values (not display labels). */
export interface OwnProfile {
  profile_code: string;
  status: ProfileStatus;
  review_note: string;
  submitted_at: string | null;
  identity_locked: boolean;
  /** PROFILE_MAX_PHOTOS on the server. */
  max_photos: number;
  completion: Completion;
  missing_for_review: string[];
  created_for: string;
  display_name: string;
  gender: "male" | "female";
  date_of_birth: string;
  height_cm: number | null;
  marital_status: string;
  religion: string;
  community: string;
  mother_tongue: string;
  country: string;
  state: string;
  district: string;
  city: string;
  native_place: string;
  about: string;
  highest_education: string;
  education_detail: string;
  institution: string;
  occupation: string;
  employment_type: string;
  work_location: string;
  annual_income: string;
  income_visible: boolean;
  family_type: string;
  family_values: string;
  family_location: string;
  father_occupation: string;
  mother_occupation: string;
  siblings: string;
  diet: string;
  hobbies: string[];
  interests: string[];
  languages: string[];
  visibility: "members" | "hidden";
  photo_visibility: "members" | "accepted";
  partner_preference: PartnerPreference;
}

export type OwnProfileField = Exclude<
  keyof OwnProfile,
  | "profile_code"
  | "status"
  | "review_note"
  | "submitted_at"
  | "identity_locked"
  | "max_photos"
  | "completion"
  | "missing_for_review"
  | "partner_preference"
>;

export interface OwnPhoto {
  id: string;
  url: string;
  width: number;
  height: number;
  is_primary: boolean;
  status: PhotoStatus;
  review_note: string;
  created_at: string;
}

export interface PhotoRef {
  url: string;
  width: number;
  height: number;
}

/** Another member as shown in lists (display labels, privacy-filtered). */
export interface MemberCard {
  profile_code: string;
  display_name: string;
  gender: "male" | "female";
  age: number;
  height_cm: number | null;
  marital_status: string;
  religion: string;
  community: string;
  education: string;
  occupation: string;
  location: { city: string; district: string; state: string; country: string };
  photo: PhotoRef | null;
  photos_hidden: boolean;
}

/** The other member in an interest or shortlist entry; `available: false` once they're no longer visible. */
export type OtherMember =
  | (MemberCard & { available: true })
  | { profile_code: string; display_name: string; available: false };

export interface InterestItem {
  id: string;
  status: InterestStatus;
  created_at: string;
  responded_at: string | null;
  profile: OtherMember;
  direction?: "sent" | "received";
}

export interface ShortlistItem {
  created_at: string;
  profile: OtherMember;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Subscription {
  id: string;
  plan_code: "diamond" | "platinum" | "royal";
  plan_name: string;
  status: "pending" | "active" | "expired" | "upcoming" | "cancelled";
  starts_at: string | null;
  ends_at: string | null;
  validity_months: number;
  contact_view_limit: number | null;
  contact_views_used: number | null;
}

export interface MembershipInfo {
  current: Subscription | null;
  history: Subscription[];
  online_payment_available: boolean;
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string;
  created_at: string;
  read: boolean;
}

export interface DashboardSummary {
  member: { first_name: string; phone_verified: boolean };
  membership: Subscription | null;
  notifications: { unread: number; recent: NotificationItem[] };
  profile: {
    profile_code: string;
    display_name: string;
    status: ProfileStatus;
    review_note: string;
    completion: Completion;
    missing_for_review: string[];
    photo: { url: string; status: PhotoStatus } | null;
    photo_count: number;
  } | null;
  interests: {
    received: number;
    awaiting_your_response: number;
    sent: number;
    sent_pending: number;
    accepted: number;
  } | null;
  shortlisted: number;
  recent_interests: InterestItem[];
}

/** GET /dashboard/shell-data (Next.js route): live values for the dashboard frame. */
export interface ShellData {
  name: string;
  profileCode: string | null;
  photoUrl: string | null;
  membership: string | null;
  unreadNotifications: number;
  awaitingReply: number;
}

/** GET /profiles/<code>/: another member's full profile, privacy-filtered. */
export interface MemberProfileDetail extends MemberCard {
  mother_tongue: string;
  native_place: string;
  about: string;
  photos: PhotoRef[];
  career: {
    qualification: string;
    institution: string;
    profession: string;
    employment_type: string;
    work_location: string;
    annual_income: string;
  };
  family: {
    type: string;
    values: string;
    location: string;
    father_occupation: string;
    mother_occupation: string;
    siblings: string;
  };
  lifestyle: { diet: string; hobbies: string[]; interests: string[]; languages: string[] };
  partner_preferences: {
    age_range: [number, number] | null;
    height_range_cm: [number, number] | null;
    marital_status: string;
    religion: string;
    education: string;
    location: string;
    notes: string;
  };
  viewer: {
    is_own_profile: boolean;
    interest_sent: { id: string; status: InterestStatus } | null;
    interest_received: { id: string; status: InterestStatus } | null;
    shortlisted: boolean;
  };
}
