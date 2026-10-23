import type { Metadata } from "next";

import { LegalDocument } from "@/features/legal/components/legal-document";
import { legalConfig } from "@/features/legal/config";
import { termsSections } from "@/features/legal/terms";

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description:
    "The terms for using Massil Matrimony: eligibility, accounts and profiles, acceptable use, membership packages, safety and how to raise a complaint.",
  // Kept out of search results until the draft is approved (features/legal/config.ts).
  ...(!legalConfig.approvedForPublication && { robots: { index: false, follow: true } }),
};

export default function TermsPage() {
  return (
    <LegalDocument
      document="terms"
      eyebrow="Legal"
      title="Terms & Conditions"
      intro={
        <p>
          The agreement between you and Massil Matrimony when you create a profile, use the member dashboard or take
          up a membership package. Please read it together with our Privacy Policy.
        </p>
      }
      sections={termsSections}
      related={[
        {
          label: "Privacy Policy",
          href: "/privacy-policy",
          description: "How we collect, use and protect your personal information.",
        },
        { label: "Contact Us", href: "/contact", description: "Questions about these terms, your membership or a complaint." },
      ]}
    />
  );
}
