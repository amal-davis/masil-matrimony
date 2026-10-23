import type { Metadata } from "next";

import { LegalDocument } from "@/features/legal/components/legal-document";
import { legalConfig } from "@/features/legal/config";
import { privacySections } from "@/features/legal/privacy-policy";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How Massil Matrimony collects, uses, shares and protects the personal information in member accounts and matrimonial profiles, and the choices members have.",
  // Kept out of search results until the draft is approved (features/legal/config.ts).
  ...(!legalConfig.approvedForPublication && { robots: { index: false, follow: true } }),
};

export default function PrivacyPolicyPage() {
  return (
    <LegalDocument
      document="privacy"
      eyebrow="Legal"
      title="Privacy Policy"
      intro={
        <p>
          What personal information Massil Matrimony collects, why we need it, who can see your profile, and how to
          make choices about your information.
        </p>
      }
      sections={privacySections}
      related={[
        {
          label: "Terms & Conditions",
          href: "/terms-and-conditions",
          description: "The rules for using Massil Matrimony and our membership packages.",
        },
        { label: "Contact Us", href: "/contact", description: "Questions, requests about your information, or complaints." },
      ]}
    />
  );
}
