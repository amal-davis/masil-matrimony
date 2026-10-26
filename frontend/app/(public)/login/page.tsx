import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { pendingCode } from "@/features/auth/challenge";
import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { LoginForm } from "@/features/auth/components/login-form";
import { REGISTER_PATH } from "@/features/auth/constants";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";

export const metadata: Metadata = {
  title: "Login",
  description: "Log in to your Massil Matrimony account with a one-time code sent to your registered mobile number.",
};

/** Reads this browser's pending-code cookie, so a refresh keeps the member on the code step. */
async function LoginWithPendingCode() {
  // The static GitHub Pages preview has no request to read.
  if (STATIC_EXPORT) return <LoginForm />;
  return <LoginForm initialPending={await pendingCode("login")} />;
}

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome Back"
      description="Registered members log in with a one-time code sent by SMS to their mobile number. No password needed."
      footer={
        <>
          <p>
            Don&apos;t have an account?{" "}
            {/* Registration is the quick form on the home page; there is no separate page yet. */}
            <Link href={REGISTER_PATH} className={authLink}>
              Register Now
            </Link>
          </p>
          <p>
            Changed your mobile number, or not receiving the SMS?{" "}
            <Link href="/contact" className={authLink}>
              Contact Us
            </Link>
          </p>
        </>
      }
    >
      <Suspense fallback={<p className="text-[0.9375rem] text-ink-muted">Loading…</p>}>
        <LoginWithPendingCode />
      </Suspense>
    </AuthShell>
  );
}
