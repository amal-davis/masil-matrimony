import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { ForgotPasswordForm } from "@/features/auth/components/forgot-password-form";
import { LOGIN_PATH } from "@/features/auth/constants";

export const metadata: Metadata = {
  title: "Forgot Password",
  description: "Get a link to set a new password for your Massil Matrimony account.",
};

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="Forgot your password?"
      description="Enter the email address on your account and we'll email you a link to set a new password. Members who used to sign in with a mobile code can set their first password here too."
      footer={
        <>
          <p>
            Remembered it?{" "}
            <Link href={LOGIN_PATH} className={authLink}>
              Back to sign in
            </Link>
          </p>
          <p>
            Don&apos;t know which email is on your account?{" "}
            <Link href="/contact" className={authLink}>
              Contact Us
            </Link>
          </p>
        </>
      }
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
