/**
 * Membership packages shown on /our-packages. This file is the single source of
 * the package copy and prices; keep it in step with the business's official
 * package sheet.
 *
 * Display only. There is no membership or payment API yet
 * (backend/apps/memberships and backend/apps/payments are placeholders), so these
 * prices must never be sent to a checkout. When payments are added, the backend
 * owns the plan ids and prices and validates them; it must not trust a price from
 * the browser.
 *
 * Brand spelling: page copy uses "Massil", the established site spelling.
 * References to the policy owner keep the supplied "Maasil Matrimony.com" until
 * the legal name is confirmed.
 */

export type PackageId = "diamond" | "platinum" | "royal";

/** A benefit line. `detail` is the longer explanation for assisted packages. */
export interface Benefit {
  title: string;
  detail?: string;
}

/** One row of the price summary. Numbers are rupee amounts; strings are shown as written. */
export interface PriceLine {
  label: string;
  value: number | string;
}

export interface MembershipPackage {
  id: PackageId;
  /** Short service-type label shown on the card, so packages differ by more than colour. */
  kind: string;
  name: string;
  subtitle?: string;
  tagline?: string;
  description: string;
  price: {
    /** Headline amount in rupees. */
    amount: number;
    /** Tax wording shown directly under the headline amount. */
    taxNote: string;
    lines: PriceLine[];
    /** Note under the price summary. */
    summaryNote?: string;
  };
  /** Validity and the other key facts, shown above the benefits. */
  facts: { label: string; value: string }[];
  benefits: Benefit[];
  /** Validity and service-agreement terms. Always visible; never collapsed. */
  terms: { title: string; body: string };
  cta: { label: string; href: string };
}

/**
 * No checkout or package-enquiry flow exists, so every package links to the
 * general contact form (POST /enquiries/), which can't carry the package choice yet.
 */
const ENQUIRY_HREF = "/contact";

export const membershipPackages: MembershipPackage[] = [
  {
    id: "diamond",
    kind: "Online Membership",
    name: "Diamond Membership",
    description:
      "An enhanced online membership for members who want additional profile discovery and communication features.",
    price: {
      amount: 12000,
      taxNote: "+ applicable GST",
      lines: [
        { label: "Membership Fee", value: 12000 },
        { label: "Applicable GST", value: "Extra" },
        { label: "Total Payable", value: "Membership fee plus applicable GST" },
      ],
    },
    facts: [
      { label: "Validity", value: "12 Months" },
      { label: "Contact access", value: "Up to 100 member contact numbers" },
    ],
    benefits: [
      { title: "Advanced Search" },
      { title: "Unlimited Interest Sending" },
      { title: "Personal Messaging" },
      { title: "Photo Viewing" },
      { title: "Profile Shortlist" },
      { title: "Who Viewed My Profile?" },
      { title: "Basic Match Suggestions" },
      { title: "Verified Profile Badge for eligible profiles" },
      { title: "Priority Profile Visibility, subject to platform availability" },
      { title: "Dedicated Matchmaking Assistance, subject to service availability" },
      {
        title:
          "Access to up to 100 member contact numbers during the membership period, subject to applicable privacy settings, member consent, and company terms",
      },
    ],
    terms: {
      title: "Validity Terms",
      body: "The Diamond Membership is valid for twelve months from the activation date. Benefits and contact access are subject to Maasil Matrimony.com's published terms and privacy policy.",
    },
    cta: { label: "Choose Diamond", href: ENQUIRY_HREF },
  },
  {
    id: "platinum",
    kind: "Assisted Matchmaking",
    name: "Platinum",
    subtitle: "Assisted Matchmaking",
    tagline: "Where Hearts Meet With Trust",
    description:
      "Personalised, staff-assisted matchmaking for members seeking dedicated guidance during their search.",
    price: {
      amount: 20000,
      taxNote: "+ applicable GST",
      lines: [
        { label: "Package Fee", value: 20000 },
        { label: "Applicable GST", value: "Extra" },
        { label: "Total Payable", value: "Package fee plus applicable GST" },
      ],
    },
    facts: [
      { label: "Validity", value: "3 Months" },
      { label: "Service type", value: "Personalised, Staff-Assisted Matchmaking" },
    ],
    benefits: [
      {
        title: "Free Online Registration",
        detail:
          "Members receive free online registration and a personal member ID to access their profile and available platform features.",
      },
      {
        title: "Dedicated Matchmaker",
        detail: "A designated Massil matchmaking staff member assists the member throughout the service period.",
      },
      {
        title: "Personalised Profile Search",
        detail:
          "The matchmaker understands the member's preferences, searches for suitable profiles, and assists with shortlisting potential matches.",
      },
      {
        title: "Interest Management",
        detail:
          "Members can express interest through their online account. The matchmaker assists in coordinating mutual interest and follow-up.",
      },
      {
        title: "Contact & Communication Coordination",
        detail:
          "The assigned matchmaker coordinates contact exchange and communication with prospective matches and families, subject to consent and privacy requirements.",
      },
      {
        title: "Follow-up Assistance",
        detail:
          "The matchmaker assists with follow-ups and coordinates further discussions when both parties are interested.",
      },
      {
        title: "Privacy & Confidentiality",
        detail:
          "Member information is handled in accordance with Maasil Matrimony.com's privacy policy. Contact details are shared only with appropriate consent.",
      },
    ],
    terms: {
      title: "Service Terms",
      body: "The package is valid for three months from the activation date. The scope of staff assistance, service hours, profile shortlisting, and communication arrangements will be specified in the Platinum service agreement.",
    },
    cta: { label: "Enquire About Platinum", href: ENQUIRY_HREF },
  },
  {
    id: "royal",
    kind: "At-Home Matchmaking",
    name: "Royal",
    subtitle: "Exclusive At-Home Matchmaking",
    description:
      "An exclusive, high-touch matchmaking service designed for busy professionals, entrepreneurs, business leaders, and families seeking a discreet, personalised experience.",
    price: {
      amount: 118000,
      taxNote: "Including 18% GST at the stated rate. Final tax treatment is subject to the applicable GST rate.",
      lines: [
        { label: "Annual Service Fee", value: 100000 },
        { label: "GST at 18%", value: 18000 },
        { label: "Total Annual Fee", value: 118000 },
      ],
      summaryNote: "The final tax amount will be based on the GST rate applicable to the service.",
    },
    facts: [
      { label: "Validity", value: "12 Months" },
      { label: "Service type", value: "Exclusive At-Home Matchmaking" },
    ],
    benefits: [
      {
        title: "Exclusive Personalised Service",
        detail:
          "Massil Royal is an exclusive, high-touch matchmaking service designed for busy professionals, business leaders, entrepreneurs, celebrities, and families seeking a discreet and personalised matchmaking experience.",
      },
      {
        title: "At-Home Matchmaking",
        detail:
          "A designated Massil matchmaking representative visits the member's residence at mutually agreed, convenient times to understand their preferences and present carefully shortlisted matrimonial profiles.",
      },
      {
        title: "Personalised Profile Curation",
        detail:
          "The Massil team identifies potential matches based on the member's preferences, family expectations, and agreed selection criteria. Members are not required to independently search through profiles online.",
      },
      {
        title: "Dedicated Matchmaker",
        detail:
          "A designated matchmaking representative coordinates profile selection, expressions of interest, communication, and follow-up throughout the service period.",
      },
      {
        title: "Family Coordination",
        detail:
          "With the consent of both parties, Massil assists in coordinating introductions, family discussions, and subsequent meetings.",
      },
      {
        title: "Privacy & Confidentiality",
        detail:
          "Member information, preferences, and family details are handled confidentially under the company's privacy policy. Profiles and contact details are shared only with appropriate permission.",
      },
    ],
    terms: {
      title: "Annual Service Validity",
      body: "The Royal package is valid for twelve months from the activation date. Home visits, service hours, travel arrangements, the number of shortlisted profiles, and other service limits will be specified in the signed service agreement.",
    },
    cta: { label: "Enquire About Royal", href: ENQUIRY_HREF },
  },
];

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Indian grouping with the rupee sign: 118000 → "₹1,18,000". */
export function formatInr(amount: number): string {
  return `₹${inr.format(amount)}`;
}
