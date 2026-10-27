"use client";

import { useState, useTransition } from "react";

import { decideContactExchange } from "../actions";
import type { ContactExchangeItem } from "../types";
import { primaryButton, secondaryButton } from "./ui";

/**
 * The member's own decision on a contact exchange. The API checks that they
 * are one of its two members and that it is still open; numbers are only ever
 * returned by the API once both consented.
 */
export function ConsentControls({ exchange }: { exchange: Pick<ContactExchangeItem, "id" | "status" | "my_decision"> }) {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");
  if (exchange.status !== "pending") return null;

  const decide = (decision: "grant" | "decline" | "withdraw") =>
    start(async () => {
      setError("");
      const result = await decideContactExchange(exchange.id, decision);
      if (!result.ok) setError(result.message);
    });

  return (
    <div className="mt-4">
      {exchange.my_decision === "pending" ? (
        <div className="flex flex-wrap gap-3">
          <button type="button" disabled={busy} onClick={() => decide("grant")} className={primaryButton}>
            I consent
          </button>
          <button type="button" disabled={busy} onClick={() => decide("decline")} className={secondaryButton}>
            Decline
          </button>
        </div>
      ) : exchange.my_decision === "granted" ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-ink-muted">You consented. Numbers are shared once the other member consents too.</p>
          <button type="button" disabled={busy} onClick={() => decide("withdraw")} className={secondaryButton}>
            Withdraw consent
          </button>
        </div>
      ) : null}
      <p role="alert" className="mt-2 text-sm text-danger empty:hidden">
        {error}
      </p>
    </div>
  );
}
