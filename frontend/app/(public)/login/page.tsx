import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Container } from "@/components/ui/container";
import { LockIcon, ShieldCheckIcon } from "@/components/ui/icons";
import { LoginFlow } from "@/features/auth/components/login-flow";

import monogram from "@/public/images/masil-matrimony-monogram.png";

export const metadata: Metadata = {
  title: "Login",
  description: "Sign in to your Massil Matrimony account using your registered mobile number.",
};

const link =
  "rounded-sm font-medium text-wine-600 underline underline-offset-4 transition-colors hover:text-wine-800 focus-visible:outline-wine-600";

/** Wine panel beside the form on large screens. Decorative and reassuring; nothing here is needed to sign in. */
function BrandPanel() {
  return (
    <div className="relative isolate hidden flex-col justify-between overflow-hidden bg-wine-800 p-12 text-ivory lg:flex">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(80%_60%_at_50%_0%,rgba(210,165,74,0.16),transparent_70%)]"
      />
      <div>
        <Image
          src={monogram}
          alt=""
          className="h-20 w-auto drop-shadow-[0_18px_28px_rgba(0,0,0,0.45)]"
          sizes="96px"
        />
        <p className="mt-8 text-[1.75rem] leading-snug font-medium text-balance text-ivory">
          Where two families become one.
        </p>
        <div aria-hidden="true" className="mt-6 flex items-center gap-3">
          <span className="h-px w-10 bg-gold/60" />
          <span className="size-1.5 rotate-45 bg-gold" />
          <span className="h-px w-10 bg-gold/60" />
        </div>
      </div>

      <ul className="mt-12 flex flex-col gap-5 text-[0.9375rem] leading-relaxed text-ivory/85">
        <li className="flex items-start gap-3">
          <LockIcon className="mt-0.5 size-5 shrink-0 text-gold" />
          No password to remember: sign in with a one-time code sent by SMS.
        </li>
        <li className="flex items-start gap-3">
          <ShieldCheckIcon className="mt-0.5 size-5 shrink-0 text-gold" />
          Each code works once and expires within minutes.
        </li>
      </ul>
    </div>
  );
}

export default function LoginPage() {
  return (
    <section aria-labelledby="login-title" className="bg-mist py-8 sm:py-14 lg:py-20">
      <Container>
        <div className="mx-auto grid max-w-lg overflow-hidden rounded-xl border border-line bg-white lg:max-w-5xl lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <BrandPanel />

          <div className="px-5 py-8 sm:px-10 sm:py-10 lg:px-14 lg:py-14">
            <h1 id="login-title" className="text-[1.875rem] leading-tight font-semibold sm:text-4xl">
              Welcome Back
            </h1>
            <p className="mt-3 text-base leading-relaxed text-pretty text-ink-muted sm:text-[1.0625rem]">
              Sign in to your Massil Matrimony account using your registered mobile number.
            </p>

            <div className="mt-8 border-t border-line pt-8">
              <LoginFlow />
            </div>

            <div className="mt-8 flex flex-col gap-2 border-t border-line pt-6 text-[0.9375rem] text-ink-muted">
              <p>
                Don&apos;t have an account?{" "}
                {/* Registration is the quick form on the home page; there is no separate page yet. */}
                <Link href="/#register" className={link}>
                  Register Now
                </Link>
              </p>
              <p>
                Need help?{" "}
                <Link href="/contact" className={link}>
                  Contact Us
                </Link>
              </p>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
