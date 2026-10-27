"use client";

import { type FormEvent, useRef, useState, useTransition } from "react";

import { sendMessage } from "../actions";
import { primaryButton } from "./ui";

const MAX = 2000;

/** Writes a message. It appears in the conversation only after the API has stored it (the page refreshes). */
export function MessageComposer({ profileCode, name }: { profileCode: string; name: string }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, start] = useTransition();
  const field = useRef<HTMLTextAreaElement>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!body.trim()) {
      setError("Write a message first.");
      field.current?.focus();
      return;
    }
    start(async () => {
      setError("");
      const result = await sendMessage(profileCode, body);
      if (result.ok) setBody("");
      else setError(result.message);
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2" noValidate>
      <label htmlFor="message-body" className="text-sm font-medium text-ink">
        Message to {name}
      </label>
      <textarea
        ref={field}
        id="message-body"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        maxLength={MAX}
        rows={3}
        aria-invalid={error ? true : undefined}
        aria-describedby="message-hint message-error"
        className="w-full rounded-lg border border-field-line/60 bg-white px-3 py-2.5 text-base text-ink focus-visible:border-wine-600 focus-visible:outline-wine-600"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p id="message-hint" className="text-sm text-ink-muted tabular-nums">
          {body.length} / {MAX}
        </p>
        <button type="submit" disabled={busy} className={primaryButton}>
          {busy ? "Sending…" : "Send message"}
        </button>
      </div>
      <p id="message-error" role="alert" className="text-sm text-danger empty:hidden">
        {error}
      </p>
    </form>
  );
}
