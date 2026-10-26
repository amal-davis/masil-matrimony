import type { PackageCode } from "@/features/packages/packages";

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
  mother_tongues: string[];
  diets: string[];
  locations: string;
  education: string;
  occupation: string;
  notes: string;
  /** Criteria that exclude profiles that don't match; the rest only rank them. */
  must_haves: string[];
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
  contact_sharing: "hidden" | "paid_members";
  /** The member agreed to appear on the public homepage if staff highlight the profile. */
  homepage_consent: boolean;
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

/** How a match fits the member's partner preferences (GET /profiles/matches/). */
export interface MatchInfo {
  /** 0-100, or null when the member has no preferences filled in. */
  score: number | null;
  /** True statements about the member's own preferences that this profile meets. */
  reasons: string[];
  /** Preferred details this profile hasn't stated. */
  not_stated: string[];
  /** The member also meets every must-have this profile has set. */
  mutual: boolean;
}

export type MatchCard = MemberCard & { shortlisted: boolean; match: MatchInfo };

export interface MatchesPage extends Paginated<MatchCard> {
  preferences_set: boolean;
  mutual_only: boolean;
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
  plan_code: Exclude<PackageCode, "free">;
  plan_name: string;
  status: "pending" | "active" | "expired" | "upcoming" | "cancelled";
  starts_at: string | null;
  ends_at: string | null;
  /** The terms stored when the subscription was recorded; later package changes don't alter them. */
  validity_months: number | null;
  /** Fee excluding GST when recorded ("12000.00"); null for subscriptions recorded before fees were stored. */
  package_fee: string | null;
  contact_view_limit: number | null;
  contact_views_used: number | null;
}

/** What the member's current membership allows, decided by the backend. */
export interface Entitlements {
  package_code: PackageCode;
  /** Null = unlimited. */
  outgoing_interest_limit: number | null;
  /** Counted only while on a package with a limit (Free). */
  outgoing_interests_used: number | null;
  contact_view_limit: number | null;
}

export interface MembershipInfo {
  current: Subscription | null;
  history: Subscription[];
  entitlements: Entitlements;
  online_payment_available: boolean;
}

export type ContactAccess =
  | "available"
  | "viewed"
  | "profile_not_active"
  | "not_included"
  | "not_shared"
  | "limit_reached"
  | "no_number";

/** GET/POST /profiles/<code>/contact/. `phone_number` only comes back from POST. */
export interface ContactStatus {
  access: ContactAccess;
  message: string;
  limit: number | null;
  used: number | null;
  phone_number?: string;
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
/**
 * How much of a profile the API returned (backend/apps/profiles/access.py). Decided on
 * the server from the session and the member's current membership; never set in the browser.
 *   public   not signed in, and the member agreed to be shown publicly
 *   limited  signed in without a membership that includes full profiles
 *   full     an eligible membership, or the member's own profile
 */
export interface ProfileAccess {
  level: "public" | "limited" | "full";
  reason: "signed_out" | "no_membership" | "package_excludes" | "membership" | "own_profile";
}

/**
 * GET /profiles/<code>/. The basic section is always present (a visitor's public view
 * has only what the member agreed to show publicly); the remaining sections are sent
 * only with full access, so they're absent, not empty, otherwise.
 */
export interface MemberProfileDetail extends Partial<Omit<MemberCard, "profile_code" | "display_name" | "gender" | "age" | "education" | "location" | "photo" | "photos_hidden">> {
  profile_code: string;
  display_name: string;
  gender: "male" | "female";
  age: number;
  education: string;
  location: MemberCard["location"];
  photo: PhotoRef | null;
  photos_hidden: boolean;
  access: ProfileAccess;
  mother_tongue?: string;
  /** The main photo only, unless access is full. */
  photos: PhotoRef[];
  native_place?: string;
  about?: string;
  career?: {
    qualification: string;
    institution: string;
    profession: string;
    employment_type: string;
    work_location: string;
    annual_income: string;
  };
  family?: {
    type: string;
    values: string;
    location: string;
    father_occupation: string;
    mother_occupation: string;
    siblings: string;
  };
  lifestyle?: { diet: string; hobbies: string[]; interests: string[]; languages: string[] };
  partner_preferences?: {
    age_range: [number, number] | null;
    height_range_cm: [number, number] | null;
    marital_status: string;
    religion: string;
    education: string;
    location: string;
    notes: string;
  };
  /** Null for a visitor who isn't signed in. */
  viewer: {
    is_own_profile: boolean;
    interest_sent: { id: string; status: InterestStatus } | null;
    interest_received: { id: string; status: InterestStatus } | null;
    shortlisted: boolean;
    contact: ContactStatus | null;
  } | null;
}

// --- Online membership purchases (backend/apps/payments) ---------------------

export type PurchaseStatus = "awaiting_payment" | "authorized" | "paid" | "failed" | "needs_review" | "order_failed";

/** Amounts are decimal rupee strings ("118000.00") from the API; only displayed, never calculated with. */
export interface PurchaseAmounts {
  base: string;
  gst_rate: string;
  gst: string;
  total: string;
  currency: string;
}

/** What the browser passes to Razorpay Checkout. Built by the API; contains no secret. */
export interface CheckoutOptions {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill: { name: string; email: string; contact: string };
  test_mode: boolean;
}

export interface Purchase {
  reference: string;
  status: PurchaseStatus;
  status_label: string;
  package_code: string;
  package_name: string;
  validity_months: number;
  amounts: PurchaseAmounts;
  created_at: string;
  paid_at: string | null;
  failure_reason: string;
  razorpay_order_id: string | null;
  razorpay_payment_id: string | null;
  membership: { starts_at: string; ends_at: string } | null;
  receipt: { id: string; number: string } | null;
  can_pay: boolean;
  can_check_status: boolean;
  test_mode: boolean;
  /** Present on the detail endpoint when the order can (still) be paid. */
  checkout?: CheckoutOptions;
  /** The callback was valid but Razorpay couldn't be asked yet. */
  confirmation_pending?: boolean;
}

/** GET /payments/checkout/<code>/: the price from the backend and whether this member can buy it now. */
export interface CheckoutQuote {
  package: {
    code: string;
    name: string;
    description: string;
    validity_months: number;
    fee_label: string;
    terms: { title: string; body: string };
  };
  price: PurchaseAmounts | null;
  customer: { name: string; email: string | null; phone: string | null };
  available: boolean;
  blocked: { code: string; message: string } | null;
  test_mode: boolean;
}

export interface ReceiptData {
  id: string;
  title: string;
  number: string;
  issued_at: string;
  seller: { brand: string; legal_name: string; address: string; gstin: string; email: string; phone: string };
  customer: { name: string; email: string; phone: string };
  item: { package: string; description: string; validity_months: number; starts_at: string | null; ends_at: string | null };
  amounts: PurchaseAmounts;
  payment: {
    purchase_reference: string;
    razorpay_order_id: string;
    razorpay_payment_id: string;
    paid_at: string;
    test_mode: boolean;
  };
}
