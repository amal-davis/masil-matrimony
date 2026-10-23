import { contactEmail, contactPhone, officeAddress } from "@/lib/site";

/**
 * Settings shared by the legal pages: Privacy Policy, Terms & Conditions,
 * Refund & Cancellation Policy and Shipping & Delivery Policy.
 *
 * Both documents describe only what the website and API actually do today.
 * Anything the business has not decided or confirmed is a `PendingDecision`
 * below: it is shown on the page as a clearly marked "To be confirmed" note,
 * never filled with an invented policy. Resolve every entry, then have both
 * documents reviewed by an Indian legal professional, before setting
 * `approvedForPublication` to true.
 */
export const legalConfig = {
  /** "Last updated" date of each document (YYYY-MM-DD). Change a document's date whenever its text changes. */
  lastUpdated: {
    privacy: "2026-10-23",
    terms: "2026-10-23",
    refund: "2026-10-23",
    shipping: "2026-10-23",
  },

  /**
   * False while the documents are drafts: the pages show a "draft for review"
   * notice, are kept out of search engines and the sitemap. Set to true only
   * after legal review and once no pending decision remains.
   */
  approvedForPublication: false,

  /** Name of the business that operates the service, e.g. "Example Matrimony Private Limited". */
  legalName: null as string | null,

  /** From lib/site.ts, so the footer, Contact page and legal pages always agree. */
  address: officeAddress,
  email: contactEmail,
  phone: contactPhone,

  /**
   * Officer who handles privacy and other complaints, e.g.
   * { name: "…", designation: "Grievance Officer", email: "grievance@<domain>" }.
   */
  grievanceOfficer: null as { name: string; designation: string; email: string } | null,
} as const;

/** Display name of the service in the documents (the site's established spelling). */
export const SERVICE_NAME = "Massil Matrimony";

/**
 * Every decision the owner must make before publication. Each is rendered in
 * place by <Pending id="…" /> wherever the documents depend on it.
 */
export const pendingDecisions = {
  legalName: "the full legal name of the business that operates Massil Matrimony",
  address: "the registered or office address",
  email: "the official email address for privacy and account requests",
  grievanceOfficer: "the name, designation and contact details of the Grievance Officer, and the response timelines",
  hosting: "the hosting provider and the country where member data is stored, including backups",
  emailProvider: "the email service used to send account emails",
  smsProvider: "whether SMS is used (for example sign-in codes or alerts) and, if so, the SMS provider",
  dataSale: "a statement of whether member data is ever sold, rented or shared for others' marketing",
  retention: "how long account, profile, photo, enquiry and log data is kept after an account is closed, and how backups are handled",
  deletionProcess: "how account closure and deletion requests are verified and how long they take",
  verification: "what the \"Verified Profile Badge\" checks, how it is earned, and what it does not confirm",
  payments: "how membership fees are paid (methods, payment provider, invoices and GST receipts)",
  refunds:
    "the refund rules for each package: whether unused fees are refundable, any permitted deductions or cancellation charges, and the conditions for accepting a cancellation",
  refundTimeline: "when an approved refund is initiated, and any legally required timelines",
  onlinePayments:
    "the payment gateway and online checkout. Memberships can't be bought on the website yet (packages are activated by our team after payment), so this wording depends on online payments being introduced or the text being revised",
  activation: "how and when a membership is activated after payment, and how payment confirmations and receipts are sent",
  assistedTimeline: "the onboarding and appointment timelines for the Platinum and Royal services, to be shown before purchase",
  phone: "the official customer-support phone number",
  renewals: "whether and how memberships renew, and what happens when one expires",
  pricingChanges: "how fee changes are announced and whether they affect active memberships",
  assistedScope: "the published scope of the Platinum and Royal services (service hours, number of profiles, home visits, travel), or confirmation that it is set only in each signed service agreement",
  marketing: "whether promotional emails or messages will be sent and how members opt out",
  governingLaw: "the governing law and the city whose courts have jurisdiction, and any dispute-resolution step before going to court",
  liability: "any limitation of liability or indemnity wording, to be drafted by a lawyer",
} as const;

export type PendingDecision = keyof typeof pendingDecisions;

/** "23 October 2026". UTC, so server and browser always agree. */
export function formatLegalDate(isoDate: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${isoDate}T00:00:00Z`),
  );
}
