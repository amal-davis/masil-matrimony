/**
 * Navigation for the public website. Add routes here as pages are built.
 *
 * Every route listed here exists.
 */
export const mainNav = [
  { label: "Home", href: "/" },
  { label: "About Us", href: "/about-us" },
  { label: "Success Stories", href: "/success-stories" },
  { label: "Membership", href: "/our-packages" },
  { label: "Contact Us", href: "/contact" },
] as const;

/** Header actions. `logout` is a POST-only route handler (app/auth/logout/route.ts), shown once signed in. */
export const headerActions = {
  search: { label: "Search profiles", href: "/search" },
  login: { label: "Login", href: "/login" },
  logout: { label: "Log out", href: "/auth/logout" },
  dashboard: { label: "My Dashboard", href: "/dashboard" },
} as const;

/**
 * Footer quick links: only destinations that exist.
 */
export const footerLinks = [
  { label: "Home", href: "/" },
  { label: "About Us", href: "/about-us" },
  { label: "Search Profiles", href: "/search" },
  { label: "How It Works", href: "/#how-it-works" },
  { label: "Success Stories", href: "/success-stories" },
  { label: "Membership Packages", href: "/our-packages" },
  { label: "FAQs", href: "/faq" },
  { label: "Contact Us", href: "/contact" },
] as const;

/** Legal pages for the footer's bottom bar (content in features/legal/). */
export const legalLinks: ReadonlyArray<{ label: string; href: string }> = [
  { label: "Privacy Policy", href: "/privacy-policy" },
  { label: "Terms & Conditions", href: "/terms-and-conditions" },
  { label: "Refund & Cancellation Policy", href: "/refund-policy" },
  { label: "Shipping & Delivery Policy", href: "/shipping-policy" },
];

/**
 * Official office address, one line per entry. NOT CONFIRMED YET: replace
 * `null` with the real address (e.g. ["Building, Street", "City, District", "Kerala 680001"]).
 * When set, the footer also offers a "View on map" link.
 */
export const officeAddress: readonly string[] | null = null;

/**
 * Official contact email, shown on the Contact page as a mailto: link.
 * NOT CONFIRMED YET: replace `null` with the real address, e.g. "support@<domain>".
 */
export const contactEmail: string | null = null;

/**
 * Official contact phone number, shown on the Contact page as a tel: link.
 * NOT CONFIRMED YET: replace `null` with the real number, e.g.
 * { display: "+91 98765 43210", tel: "+919876543210" } (`tel` in E.164, digits only after "+").
 */
export const contactPhone: { display: string; tel: string } | null = null;

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
