import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLink } from "@/features/auth/components/auth-shell";
import { LoginForm } from "@/features/auth/components/login-form";

export const metadata: Metadata = {
  title: "Login",
  description: "Sign in to your Massil Matrimony account with your email address and password.",
};

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome Back"
      description="Registered members can sign in with their email address and password to continue their search."
      footer={
        <>
          <p>
            Don&apos;t have an account?{" "}
            {/* Registration is the quick form on the home page; there is no separate page yet. */}
            <Link href="/#register" className={authLink}>
              Register Now
            </Link>
          </p>
          <p>
            Used to sign in with a code sent to your mobile?{" "}
            <Link href="/forgot-password" className={authLink}>
              Set your password
            </Link>{" "}
            using the email address on your account.
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
      <LoginForm />
    </AuthShell>
  );
}
