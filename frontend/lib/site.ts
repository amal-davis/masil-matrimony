/**
 * Navigation for the public website. Add routes here as pages are built.
 *
 * Only "/" exists today. The other hrefs are the planned public routes and
 * return the 404 page until those pages are added.
 */
export const mainNav = [
  { label: "Home", href: "/" },
  { label: "About Us", href: "/about" },
  { label: "Success Stories", href: "/success-stories" },
  { label: "Membership", href: "/membership" },
  { label: "Contact Us", href: "/contact" },
] as const;

/** Header actions. Both pages are planned and not built yet. */
export const headerActions = {
  search: { label: "Search profiles", href: "/search" },
  login: { label: "Login", href: "/login" },
} as const;

/**
 * Footer quick links: only destinations that exist. Add "About Us" (/about) and
 * "Contact Us" (/contact) here once those pages are built.
 */
export const footerLinks = [
  { label: "Home", href: "/" },
  { label: "Search Profiles", href: "/search" },
  { label: "How It Works", href: "/#how-it-works" },
  { label: "Success Stories", href: "/#success-stories" },
  { label: "FAQs", href: "/faq" },
] as const;

/**
 * Legal pages for the footer's bottom bar. Empty until /privacy and /terms are
 * published; add them as { label: "Privacy Policy", href: "/privacy" } etc.
 */
export const legalLinks: ReadonlyArray<{ label: string; href: string }> = [];

/**
 * Official office address, one line per entry. NOT CONFIRMED YET: replace
 * `null` with the real address (e.g. ["Building, Street", "City, District", "Kerala 680001"]).
 * When set, the footer also offers a "View on map" link.
 */
export const officeAddress: readonly string[] | null = null;

export type SocialPlatform = "instagram" | "facebook" | "youtube" | "whatsapp";

/**
 * Social media icons shown in the footer, in order. NO ACCOUNTS CONFIRMED YET:
 * an entry with `url: null` shows its icon as a non-clickable "coming soon"
 * placeholder. Set the brand's real profile URL to turn it into a link, e.g.
 * { platform: "instagram", url: "https://www.instagram.com/<handle>/" }.
 */
export const socialLinks: ReadonlyArray<{ platform: SocialPlatform; url: string | null }> = [
  { platform: "instagram", url: null },
  { platform: "facebook", url: null },
  { platform: "youtube", url: null },
  { platform: "whatsapp", url: null },
];
