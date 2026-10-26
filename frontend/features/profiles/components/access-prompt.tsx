import Link from "next/link";

import { LockIcon } from "@/components/ui/icons";
import { loginUrl, REGISTER_PATH } from "@/features/auth/constants";
import type { ProfileAccess } from "@/features/dashboard/types";

/**
 * Shown in place of the restricted sections when the API sent only the basic section.
 * Says what unlocks more; it never unlocks anything itself (the API decides access).
 */
export function AccessPrompt({ access, name, path }: { access: ProfileAccess; name: string; path: string }) {
  const button =
    "inline-flex h-12 items-center justify-center rounded-md px-6 text-base font-medium transition-colors focus-visible:outline-wine-600";
  const signedOut = access.level === "public";
  return (
    <section
      aria-labelledby="access-prompt-title"
      className="mt-6 flex flex-col items-center rounded-xl border border-accent-400 bg-accent-100/60 px-6 py-10 text-center sm:px-10"
    >
      <span aria-hidden="true" className="flex size-14 items-center justify-center rounded-full bg-white text-wine-600">
        <LockIcon className="size-7" />
      </span>
      <h2 id="access-prompt-title" className="mt-5 text-2xl font-semibold text-balance">
        {signedOut ? `See more of ${name}'s profile` : `Unlock ${name}'s full profile`}
      </h2>
      <p className="mt-3 max-w-[56ch] text-base leading-relaxed text-pretty text-ink-muted">
        {signedOut
          ? "Register free or sign in to see more details and send interest. A paid membership shows the full profile: about, family, education and career, lifestyle, partner preferences and every photo the member shares."
          : access.reason === "package_excludes"
            ? "Your current membership doesn't include full profiles. Silver, Gold, Diamond, Platinum and Royal memberships show about, family, education and career, lifestyle, partner preferences and every photo the member shares."
            : "Free members see the basic details. A paid membership shows the full profile: about, family, education and career, lifestyle, partner preferences and every photo the member shares."}
      </p>
      <div className="mt-7 flex w-full flex-col justify-center gap-3 sm:w-auto sm:flex-row">
        {signedOut ? (
          <>
            <Link href={REGISTER_PATH} className={`${button} bg-wine-600 text-white hover:bg-wine-800`}>
              Register free
            </Link>
            <Link href={loginUrl(path)} className={`${button} border border-wine-600 bg-white text-wine-600 hover:bg-brand-50`}>
              Sign in
            </Link>
          </>
        ) : (
          <Link href="/our-packages" className={`${button} bg-wine-600 text-white hover:bg-wine-800`}>
            View membership plans
          </Link>
        )}
      </div>
    </section>
  );
}
