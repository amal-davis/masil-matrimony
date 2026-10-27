"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { requestAssistance } from "../actions";
import { formatDate } from "../format";
import type { AssistanceInfo, AssistanceStatus } from "../types";
import { Badge, type BadgeTone, Card, Notice, primaryButton } from "./ui";

/** Badge colour for each case status (also used by the matchmaking service page). */
export const ASSISTANCE_TONE: Record<AssistanceStatus, BadgeTone> = {
  requested: "info",
  assigned: "brand",
  in_progress: "brand",
  awaiting_member: "info",
  follow_up: "brand",
  on_hold: "neutral",
  completed: "success",
  unavailable: "danger",
  cancelled: "neutral",
  expired: "neutral",
  requirements: "brand",
  curation: "brand",
  awaiting_review: "info",
  family: "brand",
  consult_requested: "info",
  consult_scheduled: "brand",
};

const MAX = 1000;

/**
 * Matchmaking assistance (Gold and Diamond): the member's latest request and its
 * status as recorded by staff, and the request form. It names a matchmaker only
 * once the API says one was assigned, and promises no response time.
 */
export function AssistanceCard({ assistance, profileActive }: { assistance: AssistanceInfo; profileActive: boolean }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, start] = useTransition();
  const latest = assistance.requests[0];
  const open = latest?.is_open ?? false;
  const canAsk = assistance.can_request && assistance.available && profileActive && !open;

  const ask = () =>
    start(async () => {
      setError("");
      const result = await requestAssistance(note);
      if (result.ok) setNote("");
      else setError(result.message);
    });

  return (
    <Card title="Matchmaking assistance" titleId="assistance-title">
      {latest ? (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={ASSISTANCE_TONE[latest.status]}>{latest.status_label}</Badge>
            <span className="text-sm text-ink-muted">Requested {formatDate(latest.requested_at)}</span>
          </div>
          <p className="mt-3 text-[0.9375rem] text-ink-muted">
            {latest.status === "requested"
              ? "Your request is waiting for our team to assign a matchmaker. We'll let you know when someone is assigned."
              : latest.status === "unavailable"
                ? "We couldn't offer matchmaking assistance for this request."
                : latest.status === "completed"
                  ? `${latest.matchmaker_name ?? "Your matchmaker"} completed this request on ${formatDate(latest.closed_at)}.`
                  : `${latest.matchmaker_name ?? "A Massil matchmaker"} is your matchmaker (assigned ${formatDate(latest.assigned_at)}).`}
          </p>
          {latest.message && <Notice className="mt-3">{latest.message}</Notice>}
          <Link href="/dashboard/matchmaking" className="mt-3 inline-block text-sm font-medium text-wine-600 underline underline-offset-4">
            {latest.kind === "service" ? "Open your matchmaking service" : "See updates from your matchmaker"}
          </Link>
        </div>
      ) : (
        <p className="text-[0.9375rem] text-ink-muted">
          Ask our team for help finding suitable matches. A staff matchmaker is assigned to your request when one is
          available.
        </p>
      )}

      {canAsk && (
        <div className="mt-4 flex flex-col gap-2">
          <label htmlFor="assistance-note" className="text-sm font-medium text-ink">
            What would you like help with? <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <textarea
            id="assistance-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={MAX}
            rows={3}
            className="w-full rounded-lg border border-field-line/60 bg-white px-3 py-2.5 text-base text-ink focus-visible:border-wine-600 focus-visible:outline-wine-600"
          />
          <button type="button" onClick={ask} disabled={busy} className={`${primaryButton} w-full`}>
            {busy ? "Sending request…" : latest ? "Ask for assistance again" : "Ask for matchmaking assistance"}
          </button>
        </div>
      )}
      {!assistance.included && (
        <p className="mt-3 text-sm text-ink-muted">Included with the Gold and Diamond memberships.</p>
      )}
      {assistance.can_request && !assistance.available && !open && (
        <p className="mt-3 text-sm text-ink-muted">Matchmaking assistance is currently unavailable. Please check back later.</p>
      )}
      {assistance.can_request && assistance.available && !profileActive && !open && (
        <p className="mt-3 text-sm text-ink-muted">Available once your profile has been approved.</p>
      )}
      <p role="alert" className="mt-2 text-sm text-danger empty:hidden">
        {error}
      </p>
    </Card>
  );
}
