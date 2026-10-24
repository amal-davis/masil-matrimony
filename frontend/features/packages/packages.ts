/**
 * Membership package types and display helpers.
 *
 * The packages themselves (names, fees, tax, validity, limits, benefit copy)
 * come only from the backend: GET /memberships/packages/ (see ./api.ts),
 * backed by the MembershipPackage table that staff maintain in the admin. This
 * file holds no prices. The backend also decides what a member may do; these
 * helpers only describe it.
 *
 * Brand spelling: page copy uses "Massil", the established site spelling.
 * References to the policy owner keep the supplied "Maasil Matrimony.com" until
 * the legal name is confirmed.
 */

export type PackageCode = "free" | "silver" | "gold" | "diamond" | "platinum" | "royal";
export type PackageCategory = "online" | "assisted";
export type TaxTreatment = "no_fee" | "gst_extra" | "gst_stated";

/** GET /memberships/packages/ item. Money is a decimal string in rupees ("12000.00"). */
export interface PackageDto {
  code: PackageCode;
  category: PackageCategory;
  name: string;
  subtitle: string;
  tagline: string;
  service_label: string;
  description: string;
  fee: string;
  fee_label: string;
  tax_treatment: TaxTreatment;
  stated_gst_rate: string | null;
  gst_amount: string | null;
  /** Null when it depends on the applicable GST rate, which the backend doesn't configure. */
  total_payable: string | null;
  validity_months: number | null;
  contact_view_limit: number | null;
  outgoing_interest_limit: number | null;
  benefits: { title: string; detail: string }[];
  terms: { title: string; body: string };
  cta_label: string;
}

/** A benefit line. `detail` is the longer explanation, mostly for assisted packages. */
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
  id: PackageCode;
  category: PackageCategory;
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
  taxTreatment: TaxTreatment;
  /** Percent, for packages whose price includes GST at a stated rate. */
  statedGstRate: number | null;
  validityMonths: number | null;
  contactViewLimit: number | null;
  outgoingInterestLimit: number | null;
  /** Validity and the other key facts, shown above the benefits. */
  facts: { label: string; value: string }[];
  benefits: Benefit[];
  /** Validity and service-agreement terms. Always visible; never collapsed. */
  terms: { title: string; body: string };
  cta: { label: string; href: string; note: string };
}

/**
 * No checkout exists (apps/payments is a placeholder), so paid packages link to
 * the general contact form (POST /enquiries/), which can't carry the package
 * choice yet. Free membership starts with the registration form on the home page.
 */
const ENQUIRY_HREF = "/contact";
const REGISTER_HREF = "/#register";

const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const rupees = (value: string) => Number(value);
/** "18.00" → "18". */
const percent = (value: string) => String(Number(value));

export function validityLabel(months: number | null): string {
  if (months === null) return "No fixed expiry";
  return months === 1 ? "1 month" : `${months} months`;
}

function price(dto: PackageDto): MembershipPackage["price"] {
  const fee = rupees(dto.fee);
  const feeLabel = sentence(dto.fee_label);
  switch (dto.tax_treatment) {
    case "no_fee":
      return { amount: 0, taxNote: "No fee", lines: [{ label: feeLabel, value: 0 }] };
    case "gst_stated": {
      const rate = percent(dto.stated_gst_rate ?? "0");
      return {
        amount: rupees(dto.total_payable ?? dto.fee),
        taxNote: `Including ${rate}% GST at the stated rate. Final tax treatment is subject to the applicable GST rate.`,
        lines: [
          { label: feeLabel, value: fee },
          { label: `GST at ${rate}%`, value: rupees(dto.gst_amount ?? "0") },
          { label: "Total payable", value: rupees(dto.total_payable ?? dto.fee) },
        ],
        summaryNote: "The final tax amount will be based on the GST rate applicable to the service.",
      };
    }
    case "gst_extra":
      return {
        amount: fee,
        taxNote: "+ applicable GST",
        lines: [
          { label: feeLabel, value: fee },
          { label: "Applicable GST", value: "Extra" },
          { label: "Total payable", value: `${feeLabel} plus applicable GST` },
        ],
      };
  }
}

function facts(dto: PackageDto): MembershipPackage["facts"] {
  const validity = { label: "Validity", value: validityLabel(dto.validity_months) };
  if (dto.category === "assisted") {
    return [
      validity,
      { label: "Service type", value: dto.subtitle || dto.service_label },
      { label: "Contact numbers", value: "Exchanged through your matchmaker, with consent" },
    ];
  }
  return [
    validity,
    {
      label: "Interests you can send",
      value: dto.outgoing_interest_limit === null ? "Unlimited" : `Up to ${dto.outgoing_interest_limit} in total`,
    },
    {
      label: "Contact numbers",
      value:
        dto.contact_view_limit === null ? "Not included" : `Up to ${dto.contact_view_limit} members' numbers`,
    },
  ];
}

export function toPackage(dto: PackageDto): MembershipPackage {
  const isFree = dto.tax_treatment === "no_fee";
  return {
    id: dto.code,
    category: dto.category,
    kind: dto.service_label,
    name: dto.name,
    subtitle: dto.subtitle || undefined,
    tagline: dto.tagline || undefined,
    description: dto.description,
    price: price(dto),
    taxTreatment: dto.tax_treatment,
    statedGstRate: dto.stated_gst_rate === null ? null : Number(dto.stated_gst_rate),
    validityMonths: dto.validity_months,
    contactViewLimit: dto.contact_view_limit,
    outgoingInterestLimit: dto.outgoing_interest_limit,
    facts: facts(dto),
    benefits: dto.benefits.map((item) => ({ title: item.title, detail: item.detail || undefined })),
    terms: dto.terms,
    cta: isFree
      ? { label: dto.cta_label, href: REGISTER_HREF, note: "Opens the free registration form." }
      : { label: dto.cta_label, href: ENQUIRY_HREF, note: "Opens our contact form to send an enquiry." },
  };
}

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Indian grouping with the rupee sign: 118000 → "₹1,18,000". */
export function formatInr(amount: number): string {
  return `₹${inr.format(amount)}`;
}
