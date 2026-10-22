"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { CheckIcon, CloseIcon } from "@/components/ui/icons";
import { formatHeightShort } from "@/features/profiles/format";
import { profilePath } from "@/features/profiles/paths";
import { cn } from "@/lib/utils";

import { respondToInterest, withdrawInterest } from "../actions";
import { formatMemberLocation, interestStatusFor } from "../format";
import type { InterestItem } from "../types";
import { CalendarIcon } from "./icons";
import { ConfirmDialog } from "./confirm-dialog";
import { MemberPhoto } from "./member-photo";
import { Badge, dangerButton, Notice, primaryButton, quietButton, secondaryButton } from "./ui";

type Pending = "accept" | "decline" | "withdraw" | null;

/**
 * One row of the interests inbox. Actions go to the API and the list
 * re-renders from the server's answer, so the status shown is always the stored one.
 */
export function InterestCard({ item, direction, date }: { item: InterestItem; direction: "received" | "sent"; date: string }) {
  const [confirm, setConfirm] = useState<Pending>(null);
  const [running, setRunning] = useState<Pending>(null);
  const [error, setError] = useState("");
  const [busy, start] = useTransition();
  const member = item.profile;
  const status = interestStatusFor(item.status, direction);
  const actionable = item.status === "pending" && member.available;
  const needsReply = direction === "received" && actionable;

  const run = (action: Exclude<Pending, null>) =>
    start(async () => {
      setError("");
      setRunning(action);
      const result = action === "withdraw" ? await withdrawInterest(item.id) : await respondToInterest(item.id, action);
      setConfirm(null);
      setRunning(null);
      if (!result.ok) setError(result.message);
    });

  const facts = member.available
    ? [
        `${member.age} yrs`,
        member.height_cm ? formatHeightShort(member.height_cm) : null,
        member.marital_status,
        [member.religion, member.community].filter(Boolean).join(" · "),
        member.education || member.occupation,
        formatMemberLocation(member.location),
      ].filter(Boolean)
    : [];

  return (
    <li
      className={cn(
        "rounded-xl border bg-white p-4 transition-colors sm:p-5",
        needsReply ? "border-brand-200 bg-brand-50/30" : "border-line",
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          {member.available ? (
            <Link href={profilePath(member.profile_code)} tabIndex={-1} aria-hidden="true" className="shrink-0">
              <MemberPhoto
                photo={member.photo}
                name={member.display_name}
                seed={member.profile_code}
                gender={member.gender}
                hidden={member.photos_hidden}
                className="aspect-[4/5] w-16 rounded-lg ring-1 ring-line sm:w-[4.5rem]"
              />
            </Link>
          ) : (
            <MemberPhoto photo={null} name={member.display_name} seed={member.profile_code} className="aspect-[4/5] w-16 shrink-0 rounded-lg sm:w-[4.5rem]" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {member.available ? (
                <Link
                  href={profilePath(member.profile_code)}
                  className="rounded-sm text-base font-semibold text-ink hover:text-wine-600 focus-visible:outline-wine-600"
                >
                  {member.display_name}
                </Link>
              ) : (
                <span className="text-base font-semibold">{member.display_name}</span>
              )}
              <span className="text-sm text-ink-muted">{member.profile_code}</span>
              <span className="lg:hidden">
                <Badge tone={status.tone}>{status.label}</Badge>
              </span>
            </div>
            {member.available ? (
              <p className="mt-1 text-sm leading-relaxed break-words text-ink">{facts.join(" · ")}</p>
            ) : (
              <p className="mt-1 text-sm text-ink-muted">This profile is no longer available.</p>
            )}
            <p className="mt-1.5 flex items-center gap-1.5 text-sm text-ink-muted">
              <CalendarIcon className="size-4" />
              {direction === "received" ? "Received" : "Sent"} {date}
            </p>
          </div>
        </div>

        <div className="hidden w-40 shrink-0 lg:block">
          <Badge tone={status.tone}>{status.label}</Badge>
        </div>

        <div className="flex flex-col gap-2 min-[420px]:flex-row min-[420px]:flex-wrap lg:w-auto lg:shrink-0 lg:flex-nowrap">
          {direction === "received" && actionable && (
            <>
              <button type="button" disabled={busy} onClick={() => run("accept")} className={primaryButton}>
                <CheckIcon className="size-4.5" />
                {running === "accept" ? "Accepting…" : "Accept"}
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirm("decline")} className={secondaryButton}>
                <CloseIcon className="size-4.5" />
                Decline
              </button>
            </>
          )}
          {direction === "sent" && actionable && (
            <button type="button" disabled={busy} onClick={() => setConfirm("withdraw")} className={dangerButton}>
              Withdraw
            </button>
          )}
          {member.available && (
            <Link href={profilePath(member.profile_code)} className={quietButton}>
              View profile
            </Link>
          )}
        </div>
      </div>

      <div role="alert" className="empty:hidden">
        {error && <Notice tone="danger" className="mt-3">{error}</Notice>}
      </div>

      <ConfirmDialog
        open={confirm === "decline"}
        busy={busy}
        tone="danger"
        title={`Decline ${member.display_name}'s interest?`}
        confirmLabel="Decline interest"
        onConfirm={() => run("decline")}
        onCancel={() => setConfirm(null)}
      >
        They&apos;ll be told that you declined. This can&apos;t be undone.
      </ConfirmDialog>
      <ConfirmDialog
        open={confirm === "withdraw"}
        busy={busy}
        tone="danger"
        title="Withdraw your interest?"
        confirmLabel="Withdraw interest"
        onConfirm={() => run("withdraw")}
        onCancel={() => setConfirm(null)}
      >
        {member.display_name} will no longer see this interest. You can send a new one later.
      </ConfirmDialog>
    </li>
  );
}
