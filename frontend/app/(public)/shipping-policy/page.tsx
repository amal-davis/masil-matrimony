import type { Metadata } from "next";

import { LegalDocument } from "@/features/legal/components/legal-document";
import { legalConfig } from "@/features/legal/config";
import { shippingSections } from "@/features/legal/shipping-policy";

export const metadata: Metadata = {
  title: "Shipping & Delivery Policy",
  description:
    "How Massil Matrimony delivers its digital memberships and assisted matchmaking services after payment.",
  // Kept out of search results until the draft is approved (features/legal/config.ts).
  ...(!legalConfig.approvedForPublication && { robots: { index: false, follow: true } }),
};

export default function ShippingPolicyPage() {
  return (
    <LegalDocument
      document="shipping"
      eyebrow="Legal"
      title="Shipping & Delivery Policy"
      intro={
        <p>
          Massil Matrimony memberships are digital services. This policy explains how they are delivered and activated,
          and how assisted matchmaking services are arranged.
        </p>
      }
      sections={shippingSections}
      related={[
        {
          label: "Terms & Conditions",
          href: "/terms-and-conditions",
          description: "The rules for using Massil Matrimony and our membership packages.",
        },
        {
          label: "Privacy Policy",
          href: "/privacy-policy",
          description: "How we collect, use and protect your personal information.",
        },
        { label: "Contact Us", href: "/contact", description: "Help with membership access, activation or service delivery." },
      ]}
    />
  );
}
