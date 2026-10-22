"use client";

import Link from "next/link";
import { useState, useTransition, type ReactNode } from "react";

import { HeartIcon, InfoIcon, PhoneIcon } from "@/components/ui/icons";
import { loginUrl } from "@/features/auth/constants";
import { addToShortlist, removeFromShortlist, sendInterest } from "@/features/dashboard/actions";
import type { MemberProfileDetail } from "@/features/dashboard/types";
import { cn } from "@/lib/utils";

import { BookmarkIcon, ShareIcon } from "./icons";

type Notice = { tone: "info" | "success" | "danger"; message: string; link?: { href: string; label: string } } | null;

const MEMBERSHIP_PATH = "/our-packages";
const membershipLink = { href: MEMBERSHIP_PATH, label: "View membership packages" };

/** Contact details are a membership benefit, but there is no contact-access API yet. */
const CONTACT_NOTICE: Notice = {
  tone: "info",
  message:
    "Viewing contact details online isn't available yet. Contact details are shared as part of membership packages, subject to this member's privacy settings.",
  link: membershipLink,
};

const SAMPLE_NOTICES = {
  interest: { tone: "info", message: "This is a sample profile for preview, so no interest can be sent. Nothing was sent." },
  shortlist: { tone: "info", message: "This is a sample profile for preview, so it can't be shortlisted. Nothing was saved." },
  contact: {
    tone: "info",
    message:
      "Sample profiles have no contact details. For real members, contact details are shared as part of membership packages, subject to each member's privacy settings.",
    link: membershipLink,
  },
} satisfies Record<string, Notice>;

const base =
  "inline-flex h-12 items-center justify-center gap-2 rounded-md px-5 text-[0.9375rem] font-medium transition-colors duration-200 focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:opacity-60";
const primary = cn(base, "bg-wine-600 text-white hover:bg-wine-800");
const secondary = cn(base, "border border-wine-600 bg-white text-wine-600 hover:bg-brand-50");

const INTEREST_LABEL = {
  pending: "Interest sent · awaiting response",
  accepted: "Interest accepted",
  declined: "Interest declined",
} as const;

/**
 * Profile actions.
 * - Sample profiles: every action explains that it's a sample; nothing is sent.
 * - Real profiles: Send Interest and Shortlist call the API and the page
 *   re-renders from the stored result; contact access isn't available online yet.
 */
export function ProfileActions({
  profilePath,
  profileCode,
  displayName,
  isSample,
  viewer,
}: {
  profilePath: string;
  profileCode: string;
  displayName: string;
  isSample: boolean;
  /** The signed-in member's relationship to this profile (real profiles only). */
  viewer?: MemberProfileDetail["viewer"];
}) {
  const [notice, setNotice] = useState<Notice>(null);
  const [shareStatus, setShareStatus] = useState("");
  const [busy, start] = useTransition();

  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: `${displayName}'s profile`, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setShareStatus("Profile link copied.");
    } catch (error) {
      // Closing the share sheet is not an error worth reporting.
      if (error instanceof DOMException && error.name === "AbortError") return;
      setShareStatus(`Copy this link to share the profile: ${url}`);
    }
  };

  const run = (action: () => Promise<{ ok: boolean; message?: string }>, success: string) =>
    start(async () => {
      const result = await action();
      setNotice(result.ok ? { tone: "success", message: success } : { tone: "danger", message: result.message ?? "Please try again." });
    });

  let actions: ReactNode;
  if (isSample) {
    actions = (
      <>
        <button type="button" onClick={() => setNotice(SAMPLE_NOTICES.interest)} className={cn(primary, "min-[420px]:col-span-2")}>
          <HeartIcon className="size-5" />
          Send Interest
        </button>
        <button type="button" onClick={() => setNotice(SAMPLE_NOTICES.shortlist)} className={secondary}>
          <BookmarkIcon className="size-5" />
          Add to Shortlist
        </button>
        <button type="button" onClick={() => setNotice(SAMPLE_NOTICES.contact)} className={secondary}>
          <PhoneIcon className="size-5" />
          View Contact Details
        </button>
      </>
    );
  } else if (!viewer) {
    const href = loginUrl(profilePath);
    actions = (
      <>
        <Link href={href} className={cn(primary, "min-[420px]:col-span-2")}>
          <HeartIcon className="size-5" />
          Send Interest
        </Link>
        <Link href={href} className={secondary}>
          <BookmarkIcon className="size-5" />
          Add to Shortlist
        </Link>
        <Link href={href} className={secondary}>
          <PhoneIcon className="size-5" />
          View Contact Details
        </Link>
      </>
    );
  } else if (viewer.is_own_profile) {
    return (
      <div className="flex flex-col gap-3">
        <p className="flex items-start gap-2.5 rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-[0.9375rem] text-ink">
          <InfoIcon className="mt-0.5 size-5 shrink-0 text-accent-600" />
          This is your profile, as other members see it.
        </p>
        <Link href="/dashboard/my-profile" className={cn(secondary, "self-start")}>
          Edit my profile
        </Link>
      </div>
    );
  } else {
    const sent = viewer.interest_sent && viewer.interest_sent.status !== "withdrawn" ? viewer.interest_sent : null;
    const received = viewer.interest_received && viewer.interest_received.status !== "withdrawn" ? viewer.interest_received : null;
    actions = (
      <>
        {received ? (
          <Link href="/dashboard/interests/received" className={cn(primary, "min-[420px]:col-span-2")}>
            <HeartIcon className="size-5" />
            {received.status === "pending" ? "They sent you an interest · Respond" : `Their interest: ${received.status}`}
          </Link>
        ) : sent ? (
          <button type="button" disabled className={cn(primary, "min-[420px]:col-span-2")}>
            <HeartIcon className="size-5" />
            {INTEREST_LABEL[sent.status as keyof typeof INTEREST_LABEL]}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => run(() => sendInterest(profileCode), `Interest sent to ${displayName}. You'll be notified when they reply.`)}
            className={cn(primary, "min-[420px]:col-span-2")}
          >
            <HeartIcon className="size-5" />
            {busy ? "Sending…" : "Send Interest"}
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          aria-pressed={viewer.shortlisted}
          onClick={() =>
            viewer.shortlisted
              ? run(() => removeFromShortlist(profileCode), "Removed from your shortlist.")
              : run(() => addToShortlist(profileCode), "Added to your shortlist.")
          }
          className={secondary}
        >
          <BookmarkIcon className={cn("size-5", viewer.shortlisted && "fill-current")} />
          {viewer.shortlisted ? "Shortlisted" : "Add to Shortlist"}
        </button>
        <button type="button" onClick={() => setNotice(CONTACT_NOTICE)} className={secondary}>
          <PhoneIcon className="size-5" />
          View Contact Details
        </button>
      </>
    );
  }

  return (
    <div>
      {/* Send Interest across the full width, the two secondary actions side by side beneath it. */}
      <div className="grid gap-3 min-[420px]:grid-cols-2">{actions}</div>

      {!isSample && !viewer && (
        <p className="mt-3 text-sm text-ink-muted">Sign in to send interest, shortlist or view contact details.</p>
      )}

      <div role="status" aria-live="polite">
        {notice && (
          <p
            className={cn(
              "mt-4 flex items-start gap-2.5 rounded-md border px-4 py-3 text-[0.9375rem] text-ink",
              notice.tone === "success" && "border-success/40 bg-success/5",
              notice.tone === "danger" && "border-danger/40 bg-danger/5",
              notice.tone === "info" && "border-accent-400 bg-accent-100",
            )}
          >
            <InfoIcon className="mt-0.5 size-5 shrink-0 text-accent-600" />
            <span className="min-w-0">
              {notice.message}
              {notice.link && (
                <>
                  {" "}
                  <Link href={notice.link.href} className="font-medium whitespace-nowrap text-wine-600 underline underline-offset-4 hover:text-wine-800">
                    {notice.link.label}
                  </Link>
                </>
              )}
            </span>
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1">
        <button
          type="button"
          onClick={share}
          className="inline-flex min-h-11 items-center gap-2 rounded-sm px-1 text-[0.9375rem] font-medium text-wine-600 underline-offset-4 hover:text-wine-800 hover:underline focus-visible:outline-wine-600"
        >
          <ShareIcon className="size-5" />
          Share Profile
        </button>
        <p role="status" aria-live="polite" className="min-w-0 text-sm break-all text-ink-muted">
          {shareStatus}
        </p>
      </div>
    </div>
  );
}
