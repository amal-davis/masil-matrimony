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
