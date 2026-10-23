import { formatInr, type MembershipPackage } from "@/features/packages/packages";

/**
 * "₹12,000 + applicable GST. Valid for 12 months from activation." for the
 * legal pages, built from the package data so it always matches /our-packages.
 */
export function packagePriceSummary(pkg: MembershipPackage): string {
  const validity = pkg.facts.find((fact) => fact.label === "Validity")?.value.toLowerCase();
  const price = `${formatInr(pkg.price.amount)} ${pkg.price.taxNote}`.replace(/\.$/, "");
  return validity ? `${price}. Valid for ${validity} from activation.` : `${price}.`;
}

/** "Platinum (Assisted Matchmaking)". */
export function packageTitle(pkg: MembershipPackage): string {
  return pkg.subtitle ? `${pkg.name} (${pkg.subtitle})` : pkg.name;
}
