import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { CheckEmail } from "@/features/auth/components/check-email";
import { pendingEmail } from "@/features/auth/session";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";

export const metadata: Metadata = {
  title: "Check Your Email",
  description: "Verify your email address to start using your Massil Matrimony account.",
  robots: { index: false, follow: false },
};

/** Reads this browser's pending-verification cookie and the send status, so it renders per request. */
type Params = Promise<{ status?: string | string[]; delivery?: string | string[] }>;

async function PendingVerification({ searchParams }: { searchParams: Params }) {
  // The static GitHub Pages preview has no request to read.
  if (STATIC_EXPORT) return <CheckEmail notSent={false} rateLimited={false} consoleOnly={false} />;
  const [email, params] = await Promise.all([pendingEmail(), searchParams]);
  // `delivery=console` only reflects how the API said it handled the email (development only).
  return (
    <CheckEmail
      email={email}
      notSent={params.status === "not-sent"}
      rateLimited={params.status === "rate-limited"}
      consoleOnly={params.delivery === "console"}
    />
  );
}

export default function CheckEmailPage({ searchParams }: { searchParams: Params }) {
  return (
    <AuthShell
      title="Check your email"
      description="One more step: verify your email address before you open your member dashboard."
      footer={
        <>
          <p>
            Already verified?{" "}
            <Link href="/login" className={authLink}>
              Sign in
            </Link>
          </p>
          <p>
            Need help?{" "}
            <Link href="/contact" className={authLink}>
              Contact Us
            </Link>
          </p>
        </>
      }
    >
      <Suspense fallback={<p className="text-[0.9375rem] text-ink-muted">Loading…</p>}>
        <PendingVerification searchParams={searchParams} />
      </Suspense>
    </AuthShell>
  );
}
