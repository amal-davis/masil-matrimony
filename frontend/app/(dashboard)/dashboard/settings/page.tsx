import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { FORGOT_PASSWORD_PATH } from "@/features/auth/constants";
import { maskPhoneNumber } from "@/features/auth/schema";
import { LogoutIcon } from "@/features/dashboard/components/icons";
import { PrivacySettings } from "@/features/dashboard/components/photo-privacy";
import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";
import { Badge, PageHeader, secondaryButton } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { getAccount, getOwnProfile } from "@/features/dashboard/server-api";
import { headerActions } from "@/lib/site";

export const metadata: Metadata = { title: "Account Settings" };

/** One settings group: what it is on the left, the controls on the right (stacked on phones). */
function SettingsGroup({ id, title, description, children }: { id: string; title: string; description: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4 border-b border-line py-7 first:pt-0 last:border-b-0 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-10">
      <div>
        <h2 id={id} className="text-base font-semibold">
          {title}
        </h2>
        <p className="mt-1 text-sm text-pretty text-ink-muted">{description}</p>
      </div>
      <div className="min-w-0 rounded-xl border border-line bg-white p-5 sm:p-6">{children}</div>
    </section>
  );
}

const link = "font-medium text-wine-600 underline underline-offset-4 hover:text-wine-800";

export default async function SettingsPage() {
  const [account, profile] = await Promise.all([getAccount(), getOwnProfile("/dashboard/settings")]);

  return (
    <>
      <PageHeader title="Account Settings" description="Your sign-in details, privacy and account." />
      <div>
        <SettingsGroup id="account-title" title="Account" description="The details we use to recognise you.">
          <dl className="grid gap-5 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-sm text-ink-muted">Email address (used to sign in)</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2 font-medium break-all">
                {account.email}
                {account.email_verified_at && <Badge tone="success">Verified</Badge>}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-ink-muted">Registered mobile number</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2 font-medium">
                {account.phone_number ? maskPhoneNumber(account.phone_number) : "Not added"}
                {account.phone_verified_at && <Badge tone="success">Verified</Badge>}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-ink-muted">Member since</dt>
              <dd className="mt-1 font-medium">{formatDate(account.date_joined)}</dd>
            </div>
          </dl>
          <p className="mt-5 border-t border-line pt-4 text-sm text-ink-muted">
            To change your email address or registered mobile number, please{" "}
            <Link href="/contact" className={link}>contact us</Link> so we can verify the change.
          </p>
        </SettingsGroup>

        <SettingsGroup id="privacy-title" title="Privacy" description="Choose who can see your profile and photos. Your contact details are never shown on your profile.">
          {profile ? (
            <PrivacySettings initial={{ visibility: profile.visibility, photo_visibility: profile.photo_visibility }} />
          ) : (
            <p className="text-[0.9375rem] text-ink-muted">
              Privacy settings become available once you{" "}
              <Link href="/dashboard/my-profile" className={link}>create your profile</Link>.
            </p>
          )}
        </SettingsGroup>

        <SettingsGroup id="signin-title" title="Sign-in & notifications" description="How you sign in, and how we keep you informed.">
          <ul className="flex flex-col gap-3 text-[0.9375rem]">
            <li>
              <span className="font-medium">Sign-in:</span>{" "}
              <span className="text-ink-muted">
                your email address and password. To change your password,{" "}
                <Link href={FORGOT_PASSWORD_PATH} className={link}>request a reset link</Link>; we&apos;ll email it to
                you, and changing it signs you out on every device.
              </span>
            </li>
            <li>
              <span className="font-medium">Notifications:</span>{" "}
              <span className="text-ink-muted">shown in your dashboard. Email and SMS alerts aren&apos;t available yet.</span>
            </li>
          </ul>
          {!DASHBOARD_PREVIEW && (
            <form method="post" action={headerActions.logout.href} className="mt-5 border-t border-line pt-5">
              <button type="submit" className={secondaryButton}>
                <LogoutIcon className="size-4.5" />
                Log out of this device
              </button>
            </form>
          )}
        </SettingsGroup>

        <SettingsGroup id="close-title" title="Hide or close your account" description="Take a break, or leave Massil Matrimony.">
          <p className="text-[0.9375rem] text-ink-muted">
            To hide your profile straight away, set &ldquo;Who can see my profile&rdquo; to Hidden under Privacy. To
            close your account permanently, please <Link href="/contact" className={link}>contact us</Link>; our team
            will confirm your request before anything is deleted.
          </p>
        </SettingsGroup>
      </div>
    </>
  );
}
