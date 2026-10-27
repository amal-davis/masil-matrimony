"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { profilePath } from "@/features/profiles/paths";

import { respondToSuggestion } from "../actions";
import { formatDate } from "../format";
import type { AssistanceCase, CaseSuggestion, MemberCard } from "../types";
import { ASSISTANCE_TONE } from "./assistance-card";
import { ContactExchangeCard } from "./contact-exchange-card";
import { MemberSummary } from "./member-summary";
import { Consultations, FamilyCoordination, ServicePlan } from "./royal-service";
import { Badge, Card, EmptyState, Notice, secondaryButton } from "./ui";

function SuggestionReply({ caseId, suggestion }: { caseId: string; suggestion: CaseSuggestion & { profile: MemberCard } }) {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");
  const reply = (response: "interested" | "not_interested") =>
    start(async () => {
      setError("");
      const result = await respondToSuggestion(caseId, suggestion.profile.profile_code, response);
      if (!result.ok) setError(result.message);
    });
  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          aria-pressed={suggestion.response === "interested"}
          onClick={() => reply("interested")}
          className={secondaryButton}
        >
          Interested
        </button>
        <button
          type="button"
          disabled={busy}
          aria-pressed={suggestion.response === "not_interested"}
          onClick={() => reply("not_interested")}
          className={secondaryButton}
        >
          Not interested
        </button>
        <Link href={profilePath(suggestion.profile.profile_code)} className="text-sm font-medium text-wine-600 underline underline-offset-4">
          View profile
        </Link>
      </div>
      {suggestion.response !== "pending" && (
        <p className="mt-1 text-sm text-ink-muted">
          You told your matchmaker: {suggestion.response === "interested" ? "interested" : "not interested"}.
        </p>
      )}
      <p role="alert" className="mt-1 text-sm text-danger empty:hidden">
        {error}
      </p>
    </div>
  );
}

/**
 * The member's assisted-matchmaking case, exactly as the API returns it: status,
 * matchmaker (only once staff assigned one), the service period, and what staff
 * chose to show. Internal notes never reach this page.
 */
export function MatchmakingCase({ item }: { item: AssistanceCase }) {
  const upcoming = item.follow_ups.filter((followUp) => followUp.status === "scheduled");
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="case-title" className="rounded-xl border border-line bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="case-title" className="text-lg font-semibold">
            Your matchmaking case
          </h2>
          <Badge tone={ASSISTANCE_TONE[item.status]}>{item.status_label}</Badge>
        </div>
        <dl className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-sm text-ink-muted">Matchmaker</dt>
            <dd className="mt-0.5 font-medium">{item.assigned ? item.matchmaker_name : "Not assigned yet"}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink-muted">Service started</dt>
            <dd className="mt-0.5 font-medium">{formatDate(item.service_starts_at)}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink-muted">Service until</dt>
            <dd className="mt-0.5 font-medium">{formatDate(item.service_ends_at)}</dd>
          </div>
        </dl>
        {!item.service_active ? (
          <Notice className="mt-4" role="status">
            Your membership&apos;s service period has ended. Your case history stays here. To continue, please{" "}
            <Link href="/contact" className="font-medium text-wine-600 underline underline-offset-4">
              contact us
            </Link>
            .
          </Notice>
        ) : item.status === "requested" ? (
          <Notice className="mt-4" role="status">
            Your case is awaiting assignment. We&apos;ll let you know when a matchmaker is assigned to you.
          </Notice>
        ) : item.status === "unavailable" ? (
          <Notice tone="danger" className="mt-4" role="status">
            We couldn&apos;t offer matchmaking assistance for this case. Please contact us.
          </Notice>
        ) : null}
        {item.message && <Notice className="mt-3">{item.message}</Notice>}
      </section>

      {item.features.consultations && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <ServicePlan item={item} />
          <Consultations item={item} />
        </div>
      )}
      {item.features.family && <FamilyCoordination item={item} />}

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Updates from your matchmaker" titleId="updates-title">
          {item.updates.length === 0 ? (
            <p className="text-[0.9375rem] text-ink-muted">No updates yet.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {item.updates.map((update) => (
                <li key={`${update.created_at}-${update.body.slice(0, 20)}`} className="border-l-2 border-wine-600/30 pl-3">
                  <p className="text-sm text-ink-muted">{formatDate(update.created_at)}</p>
                  <p className="text-[0.9375rem] whitespace-pre-line">{update.body}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
        <Card title="Follow-ups" titleId="follow-ups-title">
          {item.follow_ups.length === 0 ? (
            <p className="text-[0.9375rem] text-ink-muted">No follow-ups scheduled.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {[...upcoming, ...item.follow_ups.filter((followUp) => followUp.status !== "scheduled")].map((followUp, index) => (
                <li key={`${followUp.action}-${index}`} className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{followUp.action}</p>
                    <p className="text-sm text-ink-muted">
                      {followUp.due_on ? formatDate(followUp.due_on) : "Date to be arranged"}
                      {followUp.awaiting_member && " · waiting for your response"}
                    </p>
                  </div>
                  <Badge tone={followUp.status === "done" ? "success" : followUp.status === "scheduled" ? "info" : "neutral"}>
                    {followUp.status_label}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <section aria-labelledby="suggestions-title">
        <h2 id="suggestions-title" className="mb-3 text-lg font-semibold">
          Profiles suggested by your matchmaker
        </h2>
        {item.suggestions.length === 0 ? (
          <EmptyState compact title="No suggestions yet">
            Your matchmaker shares profiles here after searching from your partner preferences.
          </EmptyState>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {item.suggestions.map((suggestion, index) =>
              suggestion.profile ? (
                <li key={suggestion.profile.profile_code} className="rounded-xl border border-line bg-white p-4">
                  <MemberSummary member={{ ...suggestion.profile, available: true }}>
                    <SuggestionReply caseId={item.id} suggestion={{ ...suggestion, profile: suggestion.profile }} />
                  </MemberSummary>
                </li>
              ) : (
                <li key={`gone-${index}`} className="rounded-xl border border-dashed border-line bg-white p-4 text-[0.9375rem] text-ink-muted">
                  A profile your matchmaker suggested is no longer available.
                </li>
              ),
            )}
          </ul>
        )}
      </section>

      <section aria-labelledby="exchanges-title">
        <h2 id="exchanges-title" className="mb-3 text-lg font-semibold">
          Contact coordination
        </h2>
        {item.exchanges.length === 0 ? (
          <EmptyState compact title="No contact exchanges yet">
            When both families are ready to talk, your matchmaker asks each of you for consent before any numbers are
            shared.
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-4">
            {item.exchanges.map((exchange) => (
              <li key={exchange.id}>
                <ContactExchangeCard exchange={exchange} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
