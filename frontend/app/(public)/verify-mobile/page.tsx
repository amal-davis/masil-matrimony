import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { pendingCode } from "@/features/auth/challenge";
import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { VerifyMobile } from "@/features/auth/components/verify-mobile";
import { LOGIN_PATH } from "@/features/auth/constants";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";

export const metadata: Metadata = {
  title: "Verify Your Mobile Number",
  description: "Enter the code sent to your mobile number to create your Massil Matrimony account.",
  robots: { index: false, follow: false },
};

/** Reads this browser's pending-registration cookie, so it renders per request and survives a refresh. */
async function PendingRegistration() {
  // The static GitHub Pages preview has no request to read.
  if (STATIC_EXPORT) return <VerifyMobile />;
  return <VerifyMobile initialPending={await pendingCode("register")} />;
}

export default function VerifyMobilePage() {
  return (
    <AuthShell
      title="Verify your mobile number"
      description="One more step: enter the code we sent you by SMS. Your account is created as soon as the code is verified."
      footer={
        <>
          <p>
            Already have an account?{" "}
            <Link href={LOGIN_PATH} className={authLink}>
              Log in
            </Link>
          </p>
          <p>
            Not receiving the SMS?{" "}
            <Link href="/contact" className={authLink}>
              Contact Us
            </Link>
          </p>
        </>
      }
    >
      <Suspense fallback={<p className="text-[0.9375rem] text-ink-muted">Loading…</p>}>
        <PendingRegistration />
      </Suspense>
    </AuthShell>
  );
}
