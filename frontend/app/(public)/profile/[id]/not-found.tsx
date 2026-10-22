import Link from "next/link";

import { Container } from "@/components/ui/container";
import { UserIcon } from "@/components/ui/icons";

/** Shown for an unknown or unavailable profile code. Never falls back to another profile. */
export default function ProfileNotFound() {
  return (
    <div className="bg-mist">
      <Container className="py-14 sm:py-20">
        <div className="mx-auto max-w-lg rounded-xl border border-line bg-white px-6 py-10 text-center sm:px-10">
          <span
            aria-hidden="true"
            className="mx-auto flex size-14 items-center justify-center rounded-full bg-brand-50 text-wine-600"
          >
            <UserIcon className="size-7" />
          </span>
          <h1 className="mt-5 text-2xl font-semibold sm:text-3xl">Profile Not Found</h1>
          <p className="mt-3 text-base leading-relaxed text-pretty text-ink-muted">
            We couldn&apos;t find this profile. The link may be mistyped, or the profile may no longer be available.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link
              href="/search"
              className="inline-flex h-12 items-center justify-center rounded-md bg-wine-600 px-6 text-base font-medium text-white transition-colors hover:bg-wine-800 focus-visible:outline-wine-600"
            >
              Search Profiles
            </Link>
            <Link
              href="/"
              className="inline-flex h-12 items-center justify-center rounded-md border border-wine-600 px-6 text-base font-medium text-wine-600 transition-colors hover:bg-brand-50 focus-visible:outline-wine-600"
            >
              Back to Home
            </Link>
          </div>
        </div>
      </Container>
    </div>
  );
}
