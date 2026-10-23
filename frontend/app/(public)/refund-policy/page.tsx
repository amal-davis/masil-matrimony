import type { Metadata } from "next";

import { LegalDocument } from "@/features/legal/components/legal-document";
import { legalConfig } from "@/features/legal/config";
import { refundSections } from "@/features/legal/refund-policy";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description:
    "How Massil Matrimony handles membership cancellations, refund requests, and failed or duplicate payments.",
  // Kept out of search results until the draft is approved (features/legal/config.ts).
  ...(!legalConfig.approvedForPublication && { robots: { index: false, follow: true } }),
};

export default function RefundPolicyPage() {
  return (
    <LegalDocument
      document="refund"
      eyebrow="Legal"
      title="Refund & Cancellation Policy"
      intro={
        <p>
          How to cancel a Massil Matrimony membership or service, how refund requests are assessed, and what to do
          if a payment fails or is charged twice.
        </p>
      }
      sections={refundSections}
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
        { label: "Contact Us", href: "/contact", description: "Cancellation, refund or payment questions." },
      ]}
    />
  );
}
