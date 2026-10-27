"use client";

import { useState, useTransition } from "react";

import { VerifiedIcon } from "@/components/ui/icons";

import { requestVerification } from "../actions";
import type { VerificationStatus } from "../types";
import { formatDate } from "../format";
import { Badge, type BadgeTone, Card, Notice, primaryButton } from "./ui";

const STATUS: Record<VerificationStatus, { label: string; tone: BadgeTone }> = {
  not_requested: { label: "Not verified", tone: "neutral" },
  requested: { label: "Awaiting verification", tone: "info" },
  verified: { label: "Verified", tone: "success" },
  declined: { label: "Not verified", tone: "danger" },
};

/**
 * The Verified Profile badge: its status and, for members whose plan includes
 * it, the request. The badge is only ever granted by Massil staff after checking
 * an identity document; paying for a membership doesn't verify anyone.
 */
export function VerificationCard({
  status,
  note,
  verifiedAt,
  eligible,
  profileActive,
}: {
  status: VerificationStatus;
  note: string;
  verifiedAt: string | null;
  /** The backend's entitlements say the plan includes asking for verification. */
  eligible: boolean;
  profileActive: boolean;
}) {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");
  const canAsk = eligible && profileActive && (status === "not_requested" || status === "declined");

  const ask = () =>
    start(async () => {
      setError("");
      const result = await requestVerification();
      if (!result.ok) setError(result.message);
    });

  return (
    <Card title="Verified Profile badge" titleId="verification-title">
      <div className="flex flex-wrap items-center gap-2">
        <VerifiedIcon className="size-5 text-wine-600" aria-hidden="true" />
        <Badge tone={STATUS[status].tone}>{STATUS[status].label}</Badge>
      </div>
      <p className="mt-3 text-[0.9375rem] text-ink-muted">
        {status === "verified"
          ? `Our team verified your identity on ${formatDate(verifiedAt)}. Members see the Verified badge on your profile.`
          : status === "requested"
            ? "Our team will contact you to check an identity document. Your badge appears once they confirm it."
            : "The badge shows members that our team has checked your identity document against your profile."}
      </p>
      {status === "declined" && note && (
        <Notice tone="danger" className="mt-3">
          {note}
        </Notice>
      )}
      {canAsk && (
        <button type="button" onClick={ask} disabled={busy} className={`${primaryButton} mt-4 w-full`}>
          {busy ? "Sending request…" : status === "declined" ? "Ask again" : "Request verification"}
        </button>
      )}
      {!eligible && status !== "verified" && (
        <p className="mt-3 text-sm text-ink-muted">Available with the Silver, Gold and Diamond memberships.</p>
      )}
      {eligible && !profileActive && status !== "verified" && (
        <p className="mt-3 text-sm text-ink-muted">Available once your profile has been approved.</p>
      )}
      <p role="alert" className="mt-2 text-sm text-danger empty:hidden">
        {error}
      </p>
    </Card>
  );
}
