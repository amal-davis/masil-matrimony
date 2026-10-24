import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { VerifyEmail } from "@/features/auth/components/verify-email";

export const metadata: Metadata = {
  title: "Verify Your Email",
  description: "Verify the email address for your Massil Matrimony account.",
  // Verification links are personal: never index them, and never pass this page's URL on to other sites.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function VerifyEmailPage() {
  return (
    <AuthShell
      title="Verify your email"
      description="Confirming your email address keeps your account and your family's details safe."
      footer={
        <p>
          Need help?{" "}
          <Link href="/contact" className={authLink}>
            Contact Us
          </Link>
        </p>
      }
    >
      <VerifyEmail />
    </AuthShell>
  );
}
