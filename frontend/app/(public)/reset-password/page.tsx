import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { ResetPasswordForm } from "@/features/auth/components/reset-password-form";

export const metadata: Metadata = {
  title: "Set a New Password",
  description: "Choose a new password for your Massil Matrimony account.",
  // Reset links are personal: never index them, and never pass this page's URL on to other sites.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Set a new password"
      description="Choose a password you don't use on any other website."
      footer={
        <p>
          Need help?{" "}
          <Link href="/contact" className={authLink}>
            Contact Us
          </Link>
        </p>
      }
    >
      <ResetPasswordForm />
    </AuthShell>
  );
}
