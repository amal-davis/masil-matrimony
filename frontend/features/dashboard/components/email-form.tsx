"use client";

import { useId, useState, useTransition } from "react";

import { controlClasses, ErrorText } from "@/components/ui/form-field";
import { emailField } from "@/features/auth/schema";
import { cn } from "@/lib/utils";

import { updateEmail } from "../actions";
import { Notice, primaryButton, secondaryButton } from "./ui";

/**
 * The member's email address, where payment receipts are sent, with a way to
 * correct it. The API changes only the signed-in member's own address.
 */
export function EmailForm({ email }: { email: string | null }) {
  const id = useId();
  const [editing, setEditing] = useState(!email);
  const [value, setValue] = useState(email ?? "");
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [pending, startTransition] = useTransition();

  const save = () => {
    const parsed = emailField.safeParse(value);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message);
      return;
    }
    startTransition(async () => {
      setError(undefined);
      const result = await updateEmail(parsed.data);
      if (!result.ok) {
        setError((result.fieldErrors as Record<string, string>).email ?? result.message);
        return;
      }
      setSaved(true);
      setEditing(false);
    });
  };

  if (!editing) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-medium break-all">{email}</span>
          <button type="button" onClick={() => { setSaved(false); setEditing(true); }} className={cn(secondaryButton, "min-h-9 px-3 text-sm")}>
            Change
          </button>
        </div>
        <div role="status" aria-live="polite">
          {saved && <Notice tone="success">Saved. Future receipts go to this address.</Notice>}
        </div>
      </div>
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
      className="flex flex-col gap-3"
    >
      <label htmlFor={`${id}-email`} className="text-sm font-medium text-ink">
        Email address
      </label>
      <input
        id={`${id}-email`}
        type="email"
        inputMode="email"
        autoComplete="email"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={254}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={cn(`${id}-hint`, error && `${id}-email-error`)}
        className={controlClasses}
      />
      <ErrorText id={`${id}-email-error`} message={error} />
      <p id={`${id}-hint`} className="text-sm text-ink-muted">
        We send your payment receipts here. It isn&apos;t used to sign in.
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={pending} className={primaryButton}>
          {pending ? "Saving…" : "Save email"}
        </button>
        {email && (
          <button type="button" onClick={() => { setValue(email); setError(undefined); setEditing(false); }} disabled={pending} className={secondaryButton}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
