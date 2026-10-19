import type { ComponentType, ComponentProps } from "react";

import { HeartUsersIcon, LockIcon, MessagesIcon, ShieldCheckIcon } from "@/components/ui/icons";

export type BrandFeature = {
  title: string;
  description: string;
  Icon: ComponentType<ComponentProps<"svg">>;
};

/**
 * Editable copy for the homepage brand banner. These describe what the service
 * offers, not guarantees: keep them in line with what the business actually does.
 */
export const brandBanner = {
  name: "Massil Matrimony",
  tagline: "Meaningful Connections. Beautiful Beginnings.",
  description:
    "Find a life partner who shares your values, understands your aspirations, and complements your journey. Massil Matrimony brings people and families closer through a thoughtful matchmaking experience.",
  cta: {
    label: "Begin Your Journey",
    // The quick registration form in the homepage hero; there is no /register page yet.
    // Point this at the registration page once it exists.
    href: "#register",
  },
} as const;

export const brandFeatures: BrandFeature[] = [
  {
    title: "Verified Profiles",
    description: "Profiles reviewed for greater confidence.",
    Icon: ShieldCheckIcon,
  },
  {
    title: "Smart Match Suggestions",
    description: "Discover profiles aligned with your preferences.",
    Icon: HeartUsersIcon,
  },
  {
    title: "Privacy First",
    description: "Your personal information deserves care.",
    Icon: LockIcon,
  },
  {
    title: "Personalised Support",
    description: "Guidance throughout your matchmaking journey.",
    Icon: MessagesIcon,
  },
];
