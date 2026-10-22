import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { CheckIcon } from "@/components/ui/icons";
import { CalendarIcon, CrownIcon, LifebuoyIcon } from "@/features/dashboard/components/icons";
import { Badge, Card, Notice, PageHeader, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";
import { formatDate, subscriptionStatus } from "@/features/dashboard/format";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getMembership } from "@/features/dashboard/server-api";
import type { Subscription } from "@/features/dashboard/types";
import { formatInr, membershipPackages } from "@/features/packages/packages";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Membership & Upgrade" };

const DAY = 24 * 60 * 60 * 1000;

/**
 * Share of the validity period used and days left, from the subscription's real
 * dates and the time of this request (the page calls connection() first).
 */
function validity(subscription: Subscription) {
  if (!subscription.starts_at || !subscription.ends_at) return null;
  const now = Date.now();
  const start = new Date(subscription.starts_at).getTime();
  const end = new Date(subscription.ends_at).getTime();
  const used = Math.min(100, Math.max(0, Math.round(((now - start) / (end - start)) * 100)));
  return { used, daysLeft: Math.max(0, Math.ceil((end - now) / DAY)) };
}

/**
 * Package names, prices and benefits come from features/packages/packages.ts
 * (the same source as /our-packages). Status and dates come only from the API.
 */
export default async function MembershipPage() {
  const membership = await getMembership();
  const { current } = membership;
  const currentPackage = current ? membershipPackages.find((item) => item.id === current.plan_code) : undefined;
  // "Days left" depends on today, so this page must render per request, never at build time.
  // (The static GitHub Pages preview can only use its build date.)
  if (!STATIC_EXPORT) await connection();
  const period = current ? validity(current) : null;

  return (
    <>
      <PageHeader
        title="Membership & Upgrade"
        description="Your current plan, what it includes, and the packages available to you."
        actions={
          <Link href="/our-packages" className={secondaryButton}>
            Full package details
          </Link>
        }
      />

      <div className="flex flex-col gap-6">
        {/* Current plan */}
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section aria-labelledby="current-plan-title" className="overflow-hidden rounded-xl bg-wine-800 text-ivory">
            <div className="p-6 sm:p-7">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm text-ivory/75">Current plan</p>
                  <h2 id="current-plan-title" className="mt-1 text-2xl font-semibold text-ivory">
                    {current ? current.plan_name : "Free membership"}
                  </h2>
                </div>
                <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-gold/15 text-gold">
                  <CrownIcon className="size-6" />
                </span>
              </div>

              {current ? (
                <>
                  <div className="mt-4">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-0.5 text-[0.8125rem] font-medium text-ivory ring-1 ring-white/20 ring-inset">
                      <span aria-hidden="true" className="size-1.5 rounded-full bg-gold" />
                      {subscriptionStatus[current.status].label}
                    </span>
                  </div>
                  <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-white/15 pt-5">
                    <div>
                      <dt className="text-sm text-ivory/70">Activated</dt>
                      <dd className="mt-0.5 font-semibold text-ivory">{formatDate(current.starts_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-sm text-ivory/70">Valid until</dt>
                      <dd className="mt-0.5 font-semibold text-ivory">{formatDate(current.ends_at)}</dd>
                    </div>
                    {current.contact_view_limit !== null && (
                      <div className="col-span-2">
                        <dt className="text-sm text-ivory/70">Contact numbers viewed</dt>
                        <dd className="mt-0.5 font-semibold text-ivory tabular-nums">
                          {current.contact_views_used ?? 0} of {current.contact_view_limit}
                        </dd>
                      </div>
                    )}
                  </dl>
                  {period && (
                    <div className="mt-5">
                      <div className="flex justify-between text-sm text-ivory/80">
                        <span>Validity used</span>
                        <span className="tabular-nums">{period.daysLeft} days left</span>
                      </div>
                      <div
                        role="progressbar"
                        aria-label="Membership validity used"
                        aria-valuenow={period.used}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        className="mt-2 h-2 overflow-hidden rounded-full bg-white/15"
                      >
                        <div className="h-full rounded-full bg-gold" style={{ width: `${period.used}%` }} />
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="mt-4 text-[0.9375rem] text-ivory/85">
                  Build your profile, see matches, send and receive interests and shortlist profiles. Paid packages add
                  contact access and personal matchmaking assistance.
                </p>
              )}
            </div>
          </section>

          <Card
            title={currentPackage ? "Included in your plan" : "How to upgrade"}
            titleId="benefits-title"
          >
            {currentPackage ? (
              <ul className="flex flex-col gap-2.5">
                {currentPackage.benefits.map((benefit) => (
                  <li key={benefit.title} className="flex items-start gap-2.5 text-[0.9375rem]">
                    <span aria-hidden="true" className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-success/10 text-success">
                      <CheckIcon className="size-3.5" />
                    </span>
                    {benefit.title}
                  </li>
                ))}
              </ul>
            ) : (
              <ol className="flex flex-col gap-3 text-[0.9375rem]">
                {["Choose a package below.", "Contact our team to arrange payment.", "Your membership is activated and appears here."].map((text, index) => (
                  <li key={text} className="flex items-start gap-3">
                    <span aria-hidden="true" className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-wine-600">
                      {index + 1}
                    </span>
                    {text}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>

        <Notice>
          <strong className="font-semibold">Online payment isn&apos;t available yet.</strong> To buy, upgrade or renew a
          package, please{" "}
          <Link href="/contact" className="font-medium text-wine-600 underline underline-offset-4">
            contact us
          </Link>
          . Our team activates your membership once payment is confirmed, and it will then appear here.
        </Notice>

        {/* Packages */}
        <section aria-labelledby="packages-title">
          <h2 id="packages-title" className="mb-4 text-lg font-semibold">
            {current ? "Upgrade or renew" : "Choose a package"}
          </h2>
          <ul className="grid gap-4 md:grid-cols-3">
            {membershipPackages.map((item) => {
              const facts = item.facts.slice(0, 2);
              const isCurrent = current?.plan_code === item.id;
              return (
                <li
                  key={item.id}
                  className={cn(
                    "flex flex-col rounded-xl border bg-white p-5 sm:p-6",
                    isCurrent ? "border-wine-600 ring-4 ring-brand-50" : "border-line",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-ink-muted">{item.kind}</p>
                    {isCurrent && <Badge tone="brand">Your plan</Badge>}
                  </div>
                  <h3 className="mt-1 text-lg font-semibold">
                    {item.name}
                    {item.subtitle && <span className="block text-[0.9375rem] font-normal text-ink-muted">{item.subtitle}</span>}
                  </h3>
                  <p className="mt-4 text-[1.75rem] leading-none font-semibold tracking-tight tabular-nums">{formatInr(item.price.amount)}</p>
                  <p className="mt-1.5 text-sm text-ink-muted">{item.price.taxNote}</p>
                  <dl className="mt-4 flex flex-col gap-2 border-t border-line pt-4 text-sm">
                    {facts.map((fact) => (
                      <div key={fact.label} className="flex justify-between gap-3">
                        <dt className="text-ink-muted">{fact.label}</dt>
                        <dd className="text-right font-medium">{fact.value}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="mt-4 flex-1 text-sm text-ink-muted">{item.description}</p>
                  <Link href={item.cta.href} className={cn(isCurrent ? secondaryButton : primaryButton, "mt-5 w-full")}>
                    {isCurrent ? "Renew – contact us" : `Enquire about ${item.name}`}
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card title="Membership history" titleId="history-title" bodyClassName="p-0">
            {membership.history.length === 0 ? (
              <p className="px-5 py-8 text-center text-[0.9375rem] text-ink-muted sm:px-6">No memberships yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {membership.history.map((item) => (
                  <li key={item.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                    <div className="flex items-start gap-3">
                      <CalendarIcon className="mt-0.5 size-5 shrink-0 text-ink-muted" />
                      <div>
                        <p className="font-medium">{item.plan_name}</p>
                        <p className="text-sm text-ink-muted">
                          {item.starts_at ? `${formatDate(item.starts_at)} – ${formatDate(item.ends_at)}` : "Not yet activated"}
                        </p>
                      </div>
                    </div>
                    <Badge tone={subscriptionStatus[item.status].tone}>{subscriptionStatus[item.status].label}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <p className="border-t border-line px-5 py-3 text-sm text-ink-muted sm:px-6">
              There&apos;s no online payment history: payments are handled offline for now.
            </p>
          </Card>

          <Card title="Questions about your plan?" titleId="support-title">
            <p className="text-[0.9375rem] text-ink-muted">Our team can help you choose a package, renew, or understand your benefits.</p>
            <Link href="/dashboard/help" className={`${secondaryButton} mt-4 w-full`}>
              <LifebuoyIcon className="size-4.5" />
              Help & Support
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
