import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CheckIcon, UserIcon } from "@/components/ui/icons";
import {
  ArrowUpRightIcon,
  BellIcon,
  BookmarkIcon,
  CameraIcon,
  CrownIcon,
  InboxIcon,
  PencilIcon,
  SendIcon,
  SparkIcon,
} from "@/features/dashboard/components/icons";
import { MemberGrid } from "@/features/dashboard/components/member-grid";
import { MemberPhoto } from "@/features/dashboard/components/member-photo";
import {
  Badge,
  Card,
  EmptyState,
  primaryButton,
  ProgressBar,
  quietButton,
  secondaryButton,
  StatCard,
} from "@/features/dashboard/components/ui";
import { formatDate, interestStatusFor, profileStatus, subscriptionStatus } from "@/features/dashboard/format";
import { getDashboardSummary, getMatches } from "@/features/dashboard/server-api";
import type { DashboardSummary } from "@/features/dashboard/types";

export const metadata: Metadata = { title: "Overview" };

type Profile = NonNullable<DashboardSummary["profile"]>;

/** One sentence telling the member what to do next, from their real status and counts. */
function nextStep(profile: Profile, summary: DashboardSummary): { text: string; action?: { href: string; label: string } } {
  const awaiting = summary.interests?.awaiting_your_response ?? 0;
  switch (profile.status) {
    case "draft":
      return profile.missing_for_review.length
        ? {
            text: `Add ${profile.missing_for_review.length} more required ${profile.missing_for_review.length === 1 ? "detail" : "details"}, then submit your profile so families can find you.`,
            action: { href: "/dashboard/my-profile", label: "Complete my profile" },
          }
        : { text: "Your profile is ready. Submit it for review so other members can see it.", action: { href: "/dashboard/my-profile", label: "Submit for review" } };
    case "pending_review":
      return { text: "Our team is reviewing your profile. We'll notify you here as soon as it's approved." };
    case "rejected":
      return {
        text: profile.review_note ? `Changes requested: ${profile.review_note}` : "Our team has asked for a few changes to your profile.",
        action: { href: "/dashboard/my-profile", label: "Update my profile" },
      };
    case "suspended":
      return { text: "Your profile is suspended. Please contact us.", action: { href: "/dashboard/help", label: "Get help" } };
    default:
      return awaiting > 0
        ? {
            text: `${awaiting} ${awaiting === 1 ? "member is" : "members are"} waiting for your reply.`,
            action: { href: "/dashboard/interests/received?status=pending", label: "Review interests" },
          }
        : { text: "Your profile is live. Explore today's matches and send interests to the profiles you like.", action: { href: "/dashboard/matches", label: "Find matches" } };
  }
}

const quickActions: { label: string; href: string; icon: ReactNode }[] = [
  { label: "Edit my profile", href: "/dashboard/my-profile", icon: <PencilIcon className="size-[1.125rem]" /> },
  { label: "Manage photos", href: "/dashboard/photos", icon: <CameraIcon className="size-[1.125rem]" /> },
  { label: "Find matches", href: "/dashboard/matches", icon: <SparkIcon className="size-[1.125rem]" /> },
  { label: "Interests received", href: "/dashboard/interests/received", icon: <InboxIcon className="size-[1.125rem]" /> },
];

export default async function DashboardOverviewPage() {
  const summary = await getDashboardSummary();
  const { profile, interests, membership } = summary;
  const name = summary.member.first_name || profile?.display_name;

  if (!profile) {
    return (
      <>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">
          {name ? `Welcome, ${name}` : "Welcome to Massil Matrimony"}
        </h1>
        <p className="mt-1.5 text-[0.9375rem] text-ink-muted">Your member portal is ready. Let&apos;s start with your profile.</p>
        <div className="mt-6">
          <EmptyState
            icon={<UserIcon className="size-6" />}
            title="Create your matrimonial profile"
            action={<Link href="/dashboard/my-profile" className={primaryButton}>Create my profile</Link>}
          >
            Start with a few basic details. You can add the rest, and your photos, at your own pace.
          </EmptyState>
        </div>
      </>
    );
  }

  const matches = profile.status === "active" ? await getMatches(1) : null;
  // The API's best matches; never padded with other profiles.
  const recommended = matches?.results.slice(0, 4) ?? [];
  const step = nextStep(profile, summary);
  const status = profileStatus[profile.status];

  return (
    <div className="flex flex-col gap-6">
      {/* Welcome and identity */}
      <section aria-labelledby="welcome-title" className="overflow-hidden rounded-xl border border-line bg-white">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="flex flex-col justify-center p-5 sm:p-7">
            <h1 id="welcome-title" className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">
              Welcome back{name ? `, ${name}` : ""}
            </h1>
            <p className="mt-2 max-w-[56ch] text-[0.9375rem] text-pretty text-ink-muted">{step.text}</p>
            {step.action && (
              <div className="mt-5 flex flex-wrap gap-2">
                <Link href={step.action.href} className={primaryButton}>
                  {step.action.label}
                </Link>
                {profile.status === "active" && (
                  <Link href={`/profile/${profile.profile_code}`} className={secondaryButton}>
                    View my public profile
                  </Link>
                )}
              </div>
            )}
          </div>

          {/* Identity card */}
          <div className="border-t border-line bg-mist/60 p-5 sm:p-6 lg:border-t-0 lg:border-l">
            <div className="flex items-center gap-4">
              <MemberPhoto
                photo={profile.photo ? { url: profile.photo.url, width: 160, height: 200 } : null}
                name={profile.display_name}
                seed={profile.profile_code}
                className="aspect-[4/5] w-20 shrink-0 rounded-lg ring-1 ring-line"
              />
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold">{profile.display_name}</p>
                <p className="text-sm text-ink-muted">
                  ID <span className="font-semibold tracking-wide text-ink">{profile.profile_code}</span>
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={status.tone}>{status.label}</Badge>
                  <Badge tone={membership ? "brand" : "neutral"}>{membership ? membership.plan_name : "Free member"}</Badge>
                </div>
              </div>
            </div>
            <ProgressBar value={profile.completion.percent} label="Profile completion" className="mt-5" />
            <Link href="/dashboard/my-profile" className={`${secondaryButton} mt-4 w-full`}>
              <PencilIcon className="size-4" />
              Edit profile
            </Link>
          </div>
        </div>
      </section>

      {/* Statistics: real counts only */}
      {interests && (
        <section aria-label="Your activity" className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Interests received"
            value={interests.received}
            href="/dashboard/interests/received"
            icon={<InboxIcon className="size-5" />}
            note={interests.awaiting_your_response > 0 ? `${interests.awaiting_your_response} awaiting your reply` : undefined}
            emphasis={interests.awaiting_your_response > 0}
          />
          <StatCard
            label="Interests sent"
            value={interests.sent}
            href="/dashboard/interests/sent"
            icon={<SendIcon className="size-5" />}
            note={interests.sent_pending > 0 ? `${interests.sent_pending} awaiting a response` : undefined}
          />
          <StatCard
            label="Accepted interests"
            value={interests.accepted}
            href="/dashboard/interests/received?status=accepted"
            icon={<CheckIcon className="size-5" />}
            note="Mutual connections"
          />
          <StatCard label="Shortlisted profiles" value={summary.shortlisted} href="/dashboard/shortlisted" icon={<BookmarkIcon className="size-5" />} />
        </section>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        {/* Main column */}
        <div className="flex min-w-0 flex-col gap-6">
          <Card
            title="Recent interest activity"
            titleId="recent-interests-title"
            actions={<Link href="/dashboard/interests/received" className={quietButton}>View all</Link>}
            bodyClassName="p-0"
          >
            {summary.recent_interests.length === 0 ? (
              <p className="px-5 py-8 text-center text-[0.9375rem] text-ink-muted sm:px-6">
                No interest activity yet. Interests you send and receive will appear here.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {summary.recent_interests.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 px-5 py-3.5 sm:px-6">
                    <MemberPhoto
                      photo={item.profile.available ? item.profile.photo : null}
                      name={item.profile.display_name}
                      seed={item.profile.profile_code}
                      gender={item.profile.available ? item.profile.gender : undefined}
                      className="size-11 shrink-0 rounded-full"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[0.9375rem]">
                        <span className="font-semibold">{item.profile.display_name}</span>{" "}
                        <span className="text-ink-muted">
                          {item.direction === "sent" ? "· you sent an interest" : "· sent you an interest"}
                        </span>
                      </p>
                      <p className="text-sm text-ink-muted">
                        {item.profile.profile_code} · {formatDate(item.created_at)}
                      </p>
                    </div>
                    <Badge tone={interestStatusFor(item.status, item.direction).tone}>{interestStatusFor(item.status, item.direction).label}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {profile.status === "active" && (
            <Card
              title="Recommended for you"
              titleId="recommended-title"
              description={
                matches && !matches.preferences_set
                  ? "Newest approved profiles. Add partner preferences to see your best matches."
                  : "Your best matches from your partner preferences. The score shows how many of your preferences each profile meets."
              }
              actions={<Link href="/dashboard/matches" className={quietButton}>See all matches</Link>}
            >
              {recommended.length === 0 ? (
                <p className="py-4 text-center text-[0.9375rem] text-ink-muted">
                  No approved profile meets your must-haves right now.{" "}
                  <Link href="/dashboard/my-profile#preferences" className="font-medium text-wine-600 underline underline-offset-4">
                    Review your preferences
                  </Link>
                </p>
              ) : (
                <MemberGrid members={recommended} compact />
              )}
            </Card>
          )}

          <Card
            title="Notifications"
            titleId="notifications-title"
            actions={
              <Link href="/dashboard/notifications" className={quietButton}>
                {summary.notifications.unread > 0 ? `${summary.notifications.unread} unread` : "View all"}
              </Link>
            }
            bodyClassName="p-0"
          >
            {summary.notifications.recent.length === 0 ? (
              <p className="px-5 py-8 text-center text-[0.9375rem] text-ink-muted sm:px-6">You have no notifications yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {summary.notifications.recent.map((item) => (
                  <li key={item.id} className="flex items-start gap-3 px-5 py-3.5 sm:px-6">
                    <span
                      aria-hidden="true"
                      className={`mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full ${item.read ? "bg-surface-muted text-ink-muted" : "bg-brand-50 text-wine-600"}`}
                    >
                      <BellIcon className="size-[1.125rem]" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={item.read ? "text-[0.9375rem] text-ink" : "text-[0.9375rem] font-semibold text-ink"}>
                        {item.title}
                        {!item.read && <span className="sr-only"> (unread)</span>}
                      </p>
                      {item.body && <p className="truncate text-sm text-ink-muted">{item.body}</p>}
                    </div>
                    <span className="shrink-0 text-sm whitespace-nowrap text-ink-muted">{formatDate(item.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* Side column */}
        <aside className="flex min-w-0 flex-col gap-6" aria-label="Profile and membership">
          <Card title="Profile checklist" titleId="checklist-title" description={`${profile.completion.percent}% complete`}>
            <ProgressBar value={profile.completion.percent} label="Profile completion" showValue={false} />
            {profile.completion.missing.length === 0 ? (
              <p className="mt-4 flex items-center gap-2 text-[0.9375rem] text-success">
                <CheckIcon className="size-5" /> Every detail is filled in.
              </p>
            ) : (
              <>
                <ul className="mt-4 flex flex-col gap-2.5">
                  {profile.completion.missing.slice(0, 5).map((item) => (
                    <li key={item} className="flex items-center gap-2.5 text-[0.9375rem]">
                      <span aria-hidden="true" className="size-4 shrink-0 rounded-full border-2 border-field-line/60" />
                      {item}
                    </li>
                  ))}
                </ul>
                {profile.completion.missing.length > 5 && (
                  <p className="mt-2 text-sm text-ink-muted">and {profile.completion.missing.length - 5} more</p>
                )}
                <Link href="/dashboard/my-profile" className={`${primaryButton} mt-5 w-full`}>
                  Complete my profile
                </Link>
              </>
            )}
          </Card>

          {/* Membership */}
          <section aria-labelledby="membership-title" className="overflow-hidden rounded-xl bg-wine-800 text-ivory">
            <div className="p-5 sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 id="membership-title" className="text-base font-semibold text-ivory">
                  Membership
                </h2>
                <CrownIcon className="size-5 text-gold" />
              </div>
              {membership ? (
                <>
                  <p className="mt-3 text-xl font-semibold text-ivory">{membership.plan_name}</p>
                  <p className="mt-1 text-sm text-ivory/80">
                    {subscriptionStatus[membership.status].label} · valid until {formatDate(membership.ends_at)}
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-3 text-xl font-semibold text-ivory">Free member</p>
                  <p className="mt-1 text-sm text-ivory/80">Upgrade for contact access and personal matchmaking assistance.</p>
                </>
              )}
              <Link
                href="/dashboard/membership"
                className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-gold px-4 text-[0.9375rem] font-medium text-wine-900 transition-colors hover:bg-gold-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold"
              >
                {membership ? "Manage membership" : "Explore membership plans"}
                <ArrowUpRightIcon className="size-4" />
              </Link>
            </div>
          </section>

          <Card title="Quick actions" titleId="quick-actions-title" bodyClassName="p-2">
            <ul className="flex flex-col">
              {quickActions.map((action) => (
                <li key={action.href}>
                  <Link
                    href={action.href}
                    className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-[0.9375rem] font-medium text-ink transition-colors hover:bg-mist focus-visible:outline-wine-600"
                  >
                    <span className="flex size-8 items-center justify-center rounded-lg bg-brand-50 text-wine-600">{action.icon}</span>
                    {action.label}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </div>
  );
}
