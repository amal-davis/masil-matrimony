"use client";

import { type FormEvent, useState, useTransition } from "react";

import { addFamilyContact, consultationAction, decideFamilyContact, requestConsultation, updateRequirements } from "../actions";
import { formatDate } from "../format";
import type { AssistanceCase, Consultation, ConsultationStatus, FamilyContact } from "../types";
import { Badge, type BadgeTone, Card, primaryButton, secondaryButton } from "./ui";

const field =
  "w-full rounded-lg border border-field-line/60 bg-white px-3 py-2.5 text-base text-ink focus-visible:border-wine-600 focus-visible:outline-wine-600";
const label = "text-sm font-medium text-ink";
const timeFormat = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" });

const CONSULTATION_TONE: Record<ConsultationStatus, BadgeTone> = {
  requested: "info",
  proposed: "info",
  scheduled: "brand",
  completed: "success",
  cancelled: "neutral",
  unavailable: "danger",
};

function useAction() {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");
  const run = (action: () => Promise<{ ok: boolean; message?: string }>, onDone?: () => void) =>
    start(async () => {
      setError("");
      const result = await action();
      if (result.ok) onDone?.();
      else setError(result.message ?? "Something went wrong.");
    });
  const alert = (
    <p role="alert" className="mt-2 text-sm text-danger empty:hidden">
      {error}
    </p>
  );
  return { busy, run, alert };
}

/** The member's own requirements (editable) beside the plan and next steps their matchmaker agreed. */
export function ServicePlan({ item }: { item: AssistanceCase }) {
  const [text, setText] = useState(item.requirements);
  const { busy, run, alert } = useAction();
  const save = (event: FormEvent) => {
    event.preventDefault();
    run(() => updateRequirements(item.id, text));
  };
  return (
    <Card title="Your service plan" titleId="plan-title">
      <dl className="flex flex-col gap-4">
        <div>
          <dt className="text-sm text-ink-muted">Plan agreed with your matchmaker</dt>
          <dd className="mt-0.5 whitespace-pre-line">{item.service_plan || "Your matchmaker will agree a plan with you."}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Next steps</dt>
          <dd className="mt-0.5 whitespace-pre-line">{item.next_steps || "None recorded yet."}</dd>
        </div>
      </dl>
      {item.is_open ? (
        <form onSubmit={save} className="mt-5 flex flex-col gap-2 border-t border-line pt-4">
          <label htmlFor="requirements" className={label}>
            Your requirements, in your own words
          </label>
          <textarea id="requirements" rows={3} maxLength={1000} value={text} onChange={(event) => setText(event.target.value)} className={field} />
          <p className="text-sm text-ink-muted">Your saved partner preferences are on your profile; your matchmaker starts from them.</p>
          <button type="submit" disabled={busy} className={`${secondaryButton} self-start`}>
            {busy ? "Saving…" : "Save requirements"}
          </button>
          {alert}
        </form>
      ) : (
        item.requirements && <p className="mt-4 border-t border-line pt-4 whitespace-pre-line">{item.requirements}</p>
      )}
    </Card>
  );
}

function ConsultationRow({ caseId, consultation }: { caseId: string; consultation: Consultation }) {
  const { busy, run, alert } = useAction();
  const open = ["requested", "proposed", "scheduled"].includes(consultation.status);
  return (
    <li className="rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={CONSULTATION_TONE[consultation.status]}>{consultation.status_label}</Badge>
        <span className="text-sm text-ink-muted">Requested {formatDate(consultation.requested_at)}</span>
      </div>
      {consultation.scheduled_for && consultation.status !== "cancelled" && consultation.status !== "unavailable" && (
        <p className="mt-2 font-medium">
          {consultation.status === "proposed" ? "Proposed: " : ""}
          {timeFormat.format(new Date(consultation.scheduled_for))}
        </p>
      )}
      {consultation.message && <p className="mt-1 text-[0.9375rem]">{consultation.message}</p>}
      <p className="mt-1 text-sm text-ink-muted">
        {consultation.location_provided ? "Visit address given to your matchmaker." : "No visit address given yet."}
      </p>
      {open && (
        <div className="mt-3 flex flex-wrap gap-3">
          {consultation.status === "proposed" && (
            <button type="button" disabled={busy} onClick={() => run(() => consultationAction(caseId, consultation.id, "confirm"))} className={primaryButton}>
              Confirm this time
            </button>
          )}
          <button type="button" disabled={busy} onClick={() => run(() => consultationAction(caseId, consultation.id, "cancel"))} className={secondaryButton}>
            Cancel consultation
          </button>
        </div>
      )}
      {alert}
    </li>
  );
}

/** At-home consultations: requested here, proposed by staff, scheduled only once the member confirms. */
export function Consultations({ item }: { item: AssistanceCase }) {
  const [note, setNote] = useState("");
  const [address, setAddress] = useState("");
  const { busy, run, alert } = useAction();
  const canRequest = item.is_open && item.service_active && !item.consultations.some((c) => ["requested", "proposed", "scheduled"].includes(c.status));
  const ask = (event: FormEvent) => {
    event.preventDefault();
    run(() => requestConsultation(item.id, note, address), () => {
      setNote("");
      setAddress("");
    });
  };
  return (
    <Card title="At-home consultations" titleId="consultations-title">
      {item.consultations.length === 0 ? (
        <p className="text-[0.9375rem] text-ink-muted">No consultations yet. Nothing is booked until you confirm a time.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {item.consultations.map((consultation) => (
            <ConsultationRow key={consultation.id} caseId={item.id} consultation={consultation} />
          ))}
        </ul>
      )}
      {canRequest && (
        <form onSubmit={ask} className="mt-5 flex flex-col gap-2 border-t border-line pt-4">
          <label htmlFor="consultation-note" className={label}>
            Preferred days or times <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <input id="consultation-note" maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} className={field} />
          <label htmlFor="consultation-address" className={label}>
            Address for the visit <span className="font-normal text-ink-muted">(seen only by your matchmaking team)</span>
          </label>
          <textarea id="consultation-address" rows={2} maxLength={500} value={address} onChange={(event) => setAddress(event.target.value)} className={field} />
          <button type="submit" disabled={busy} className={`${primaryButton} self-start`}>
            {busy ? "Sending…" : "Request a consultation"}
          </button>
        </form>
      )}
      {alert}
    </Card>
  );
}

function FamilyRow({ caseId, contact }: { caseId: string; contact: FamilyContact }) {
  const { busy, run, alert } = useAction();
  return (
    <li className="rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium">
          {contact.name} <span className="font-normal text-ink-muted">({contact.relationship})</span>
        </p>
        <Badge tone={contact.permission === "granted" ? "success" : contact.permission === "pending" ? "info" : "neutral"}>
          {contact.permission_label}
        </Badge>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        Purpose: {contact.purpose}
        {contact.phone_hint && ` · ${contact.phone_hint}`}
      </p>
      {contact.permission === "pending" && <p className="mt-2 rounded-lg bg-mist px-3 py-2 text-sm">{contact.statement}</p>}
      {contact.actions.length > 0 && (
        <ul className="mt-2 text-sm">
          {contact.actions.map((action) => (
            <li key={`${action.created_at}-${action.action}`}>
              {formatDate(action.created_at)}: {action.action}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-3">
        {contact.permission !== "granted" && (
          <button type="button" disabled={busy} onClick={() => run(() => decideFamilyContact(caseId, contact.id, "grant"))} className={primaryButton}>
            Give permission
          </button>
        )}
        {contact.permission === "granted" && (
          <button type="button" disabled={busy} onClick={() => run(() => decideFamilyContact(caseId, contact.id, "withdraw"))} className={secondaryButton}>
            Withdraw permission
          </button>
        )}
      </div>
      {alert}
    </li>
  );
}

/** Family coordination: only with the member's own permission, for a stated purpose, withdrawable. */
export function FamilyCoordination({ item }: { item: AssistanceCase }) {
  const empty = { name: "", relationship: "", phone_number: "", purpose: "", permission: false };
  const [form, setForm] = useState(empty);
  const { busy, run, alert } = useAction();
  const set = (key: keyof typeof empty) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });
  const add = (event: FormEvent) => {
    event.preventDefault();
    run(() => addFamilyContact(item.id, form), () => setForm(empty));
  };
  const canAdd = item.is_open && item.service_active;
  return (
    <Card title="Family coordination" titleId="family-title">
      <p className="text-[0.9375rem] text-ink-muted">
        Your matchmaker contacts a family member only with your permission, and only for the purpose you give.
      </p>
      {item.family.length > 0 && (
        <ul className="mt-4 flex flex-col gap-3">
          {item.family.map((contact) => (
            <FamilyRow key={contact.id} caseId={item.id} contact={contact} />
          ))}
        </ul>
      )}
      {canAdd && (
        <form onSubmit={add} className="mt-5 grid gap-3 border-t border-line pt-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className={label}>Name</span>
            <input required maxLength={80} value={form.name} onChange={set("name")} className={field} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={label}>Relationship</span>
            <input required maxLength={40} value={form.relationship} onChange={set("relationship")} className={field} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={label}>
              Their phone number <span className="font-normal text-ink-muted">(optional)</span>
            </span>
            <input type="tel" maxLength={20} value={form.phone_number} onChange={set("phone_number")} className={field} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={label}>What may the matchmaker discuss with them?</span>
            <input required maxLength={300} value={form.purpose} onChange={set("purpose")} className={field} />
          </label>
          <label className="flex items-start gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={form.permission}
              onChange={(event) => setForm({ ...form, permission: event.target.checked })}
              className="mt-1"
            />
            I permit my matchmaker to contact this person for this purpose only. I can withdraw this at any time.
          </label>
          <button type="submit" disabled={busy || !form.permission} className={`${primaryButton} justify-self-start`}>
            {busy ? "Saving…" : "Give permission"}
          </button>
        </form>
      )}
      {alert}
    </Card>
  );
}
