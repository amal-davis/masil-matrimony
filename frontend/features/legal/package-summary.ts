import { formatInr, validityLabel, type MembershipPackage } from "@/features/packages/packages";

/**
 * "₹12,000 + applicable GST. Valid for 12 months from activation." for the
 * legal pages, built from the package data so it always matches /our-packages.
 */
export function packagePriceSummary(pkg: MembershipPackage): string {
  if (pkg.taxTreatment === "no_fee") {
    const interests = pkg.outgoingInterestLimit === null ? "" : ` Includes up to ${pkg.outgoingInterestLimit} outgoing interests in total.`;
    return `No fee.${interests}`;
  }
  const price = `${formatInr(pkg.price.amount)} ${pkg.price.taxNote}`.replace(/\.$/, "");
  return pkg.validityMonths === null
    ? `${price}.`
    : `${price}. Valid for ${validityLabel(pkg.validityMonths)} from activation.`;
}

/** "Platinum (Assisted Matchmaking)". */
export function packageTitle(pkg: MembershipPackage): string {
  return pkg.subtitle ? `${pkg.name} (${pkg.subtitle})` : pkg.name;
}
