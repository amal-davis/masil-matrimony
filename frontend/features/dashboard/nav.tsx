import type { ReactNode } from "react";

import { UserIcon } from "@/components/ui/icons";

import {
  BellIcon,
  BookmarkIcon,
  CameraIcon,
  CrownIcon,
  GearIcon,
  GridIcon,
  InboxIcon,
  LifebuoyIcon,
  SendIcon,
  SparkIcon,
} from "./components/icons";

/** Which real count, if any, a nav item shows as a badge (from GET /dashboard/shell-data). */
export type BadgeKey = "awaitingReply" | "unreadNotifications";

export interface DashboardNavItem {
  label: string;
  href: string;
  icon: ReactNode;
  /** Short label for the mobile bottom bar. */
  short?: string;
  badge?: BadgeKey;
}

export interface DashboardNavGroup {
  label: string;
  items: DashboardNavItem[];
}

const icon = "size-5 shrink-0";

/** The member portal's navigation, grouped by task. Every route listed here exists. */
export const dashboardNavGroups: DashboardNavGroup[] = [
  {
    label: "Main",
    items: [
      { label: "Overview", short: "Home", href: "/dashboard", icon: <GridIcon className={icon} /> },
      { label: "My Profile", short: "Profile", href: "/dashboard/my-profile", icon: <UserIcon className={icon} /> },
      { label: "Manage Photos", href: "/dashboard/photos", icon: <CameraIcon className={icon} /> },
    ],
  },
  {
    label: "Matchmaking",
    items: [
      { label: "Find Matches", short: "Matches", href: "/dashboard/matches", icon: <SparkIcon className={icon} /> },
      {
        label: "Interests Received",
        short: "Interests",
        href: "/dashboard/interests/received",
        icon: <InboxIcon className={icon} />,
        badge: "awaitingReply",
      },
      { label: "Interests Sent", href: "/dashboard/interests/sent", icon: <SendIcon className={icon} /> },
      { label: "Shortlisted Profiles", href: "/dashboard/shortlisted", icon: <BookmarkIcon className={icon} /> },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Membership & Upgrade", href: "/dashboard/membership", icon: <CrownIcon className={icon} /> },
      {
        label: "Notifications",
        href: "/dashboard/notifications",
        icon: <BellIcon className={icon} />,
        badge: "unreadNotifications",
      },
      { label: "Account Settings", href: "/dashboard/settings", icon: <GearIcon className={icon} /> },
      { label: "Help & Support", href: "/dashboard/help", icon: <LifebuoyIcon className={icon} /> },
    ],
  },
];

export const dashboardNav: DashboardNavItem[] = dashboardNavGroups.flatMap((group) => group.items);

/** The four destinations in the mobile bottom bar; everything else is in the menu. */
export const bottomNav = ["/dashboard", "/dashboard/matches", "/dashboard/interests/received", "/dashboard/my-profile"].map(
  (href) => dashboardNav.find((item) => item.href === href)!,
);

/** The nav item a path belongs to (the longest matching href). */
export function activeHref(pathname: string): string | undefined {
  return dashboardNav
    .map((item) => item.href)
    .filter((href) => pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.length - a.length)[0];
}

/** Breadcrumb trail for a path: Dashboard › group › page. */
export function breadcrumbsFor(pathname: string): { label: string; href?: string }[] {
  const href = activeHref(pathname);
  if (!href || href === "/dashboard") return [{ label: "Overview" }];
  const group = dashboardNavGroups.find((item) => item.items.some((entry) => entry.href === href))!;
  const item = group.items.find((entry) => entry.href === href)!;
  return [{ label: "Dashboard", href: "/dashboard" }, { label: group.label }, { label: item.label }];
}
