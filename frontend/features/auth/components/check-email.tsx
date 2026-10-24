"use client";

import { useEffect, useId, useState, useTransition } from "react";

import { ErrorText, errorProps } from "@/components/ui/form-field";
import { MailIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import { changeUnverifiedEmail, resendVerification } from "../actions";
import { EMAIL_MAX, PASSWORD_MAX } from "../schema";
import { authControl, NoticeBox, PasswordInput, primaryButton, Spinner, textLink, type Notice } from "./auth-ui";

/** Seconds before another link can be requested from this page. The API also caps sends per address. */
const RESEND_COOLDOWN = 60;

const secondaryButton =
  "inline-flex h-13 w-full items-center justify-center gap-2.5 rounded-md border-[1.5px] border-wine-600 bg-white px-8 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-brand-50 focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:opacity-60";

/**
 * After registering (or signing in before verifying): where the link went, a
 * resend button, and a way to correct a mistyped address. Nothing here signs
 * anyone in; the dashboard opens only after the link is used and the member signs in.
 */
export function CheckEmail({
  email: initialEmail,
  notSent,
  rateLimited,
  consoleOnly: initialConsoleOnly,
}: {
  email?: string;
  notSent: boolean;
  /** The account was created, but the address already had its hourly quota of emails. */
  rateLimited: boolean;
  /** The API printed the email to its terminal (development console backend) instead of sending it. */
  consoleOnly: boolean;
}) {
  const id = useId();
  const [email, setEmail] = useState(initialEmail);
  const [typedEmail, setTypedEmail] = useState("");
  const [notice, setNotice] = useState<Notice>(
    notSent
      ? {
          kind: "error",
          message:
            "Your account was created, but we couldn't send the verification email. Please use “Send a new link” below in a few minutes.",
        }
      : rateLimited
        ? {
            kind: "error",
            message:
              "Your account was created, but this address has already received several emails from us in the last hour, so we didn't send another. Use the newest link you received, or send a new one in about an hour.",
          }
        : null,
  );
  const [cooldown, setCooldown] = useState(notSent ? 0 : RESEND_COOLDOWN);
  const [pending, start] = useTransition();
  const [changing, setChanging] = useState(false);
  const [consoleOnly, setConsoleOnly] = useState(initialConsoleOnly);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const resend = () =>
    start(async () => {
      const result = await resendVerification(email ? undefined : typedEmail.trim());
      setNotice({ kind: result.ok ? "info" : "error", message: result.message });
      if (result.ok) {
        if (!email) setEmail(typedEmail.trim());
        setCooldown(RESEND_COOLDOWN);
        setConsoleOnly(result.consoleOnly);
      }
    });

  return (
    <div className="flex flex-col gap-6">
      {consoleOnly && (
        <p className="rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-[0.9375rem] leading-relaxed text-ink">
          <strong className="font-semibold">Development email mode.</strong> The API is using Django&apos;s console
          email backend, so this email was printed in the Django server&apos;s terminal and <em>not</em> delivered to
          the inbox. Copy the verification link from there, or set <code>EMAIL_PROVIDER=smtp</code> to send real email.
        </p>
      )}
      <div className="flex items-start gap-4 rounded-lg border border-line bg-mist px-4 py-4 sm:px-5">
        <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-wine-600">
          <MailIcon className="size-5" />
        </span>
        <div className="min-w-0 text-[0.9375rem] leading-relaxed text-ink">
          {notSent || rateLimited ? (
            // Nothing went out with this registration, so don't claim it did.
            <p>
              Your account
              {email && (
                <>
                  {" "}for <strong className="font-semibold break-all">{email}</strong>
                </>
              )}{" "}
              is waiting for email verification.
            </p>
          ) : email ? (
            <p>
              We sent a verification link to <strong className="font-semibold break-all">{email}</strong>.
            </p>
          ) : (
            <p>We sent a verification link to the email address you registered with.</p>
          )}
          <p className="mt-1 text-ink-muted">
            Open it within 24 hours to verify your address, then sign in. You need to verify your email before you can
            use your member dashboard.
          </p>
        </div>
      </div>

      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[0.9375rem] leading-relaxed text-ink-muted marker:text-wine-600">
        <li>Can&apos;t find it? Check your spam or promotions folder.</li>
        <li>If you ask for a new link, only the newest one will work.</li>
      </ul>

      <NoticeBox notice={notice} emptyOffset="-mt-6" />

      <div className="flex flex-col gap-3">
        {!email && (
          <div>
            <label htmlFor={`${id}-email`} className="block text-sm font-medium text-ink">
              Email address you registered with
            </label>
            <input
              id={`${id}-email`}
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={EMAIL_MAX}
              value={typedEmail}
              onChange={(event) => setTypedEmail(event.target.value)}
              className={cn(authControl, "mt-1.5 px-3.5")}
            />
          </div>
        )}
        <button
          type="button"
          onClick={resend}
          disabled={pending || cooldown > 0 || (!email && !typedEmail.trim())}
          className={primaryButton}
        >
          {pending && <Spinner />}
          {pending ? "Sending…" : cooldown > 0 ? `Send a new link (in ${cooldown}s)` : "Send a new link"}
        </button>
      </div>

      {email && (
        <div className="border-t border-line pt-5">
          {changing ? (
            <ChangeEmailForm
              currentEmail={email}
              onCancel={() => setChanging(false)}
              onChanged={(newEmail, printedOnly) => {
                setEmail(newEmail);
                setConsoleOnly(printedOnly);
                setChanging(false);
                setCooldown(RESEND_COOLDOWN);
                setNotice({ kind: "info", message: `We've sent a new verification link to ${newEmail}.` });
              }}
            />
          ) : (
            <p className="text-[0.9375rem] text-ink-muted">
              Typed the wrong address?{" "}
              <button type="button" onClick={() => setChanging(true)} className={textLink}>
                Change email address
              </button>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Correct the address before it's verified. The API checks the account's password first. */
function ChangeEmailForm({
  currentEmail,
  onCancel,
  onChanged,
}: {
  currentEmail: string;
  onCancel: () => void;
  onChanged: (email: string, consoleOnly: boolean) => void;
}) {
  const id = useId();
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ newEmail?: string; password?: string }>({});
  const [notice, setNotice] = useState<Notice>(null);
  const [pending, start] = useTransition();

  const submit = () =>
    start(async () => {
      setErrors({});
      setNotice(null);
      const result = await changeUnverifiedEmail(password, newEmail);
      if (result.ok) return onChanged(result.email, result.consoleOnly);
      if (result.field) setErrors({ [result.field]: result.message });
      else setNotice({ kind: "error", message: result.message });
      setPassword("");
    });

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      aria-busy={pending}
      className="flex flex-col gap-5"
    >
      <div>
        <h2 className="text-lg font-semibold text-ink">Change your email address</h2>
        <p className="mt-1 text-[0.9375rem] leading-relaxed text-ink-muted">
          Replacing <span className="font-medium break-all text-ink">{currentEmail}</span>. Enter the password you chose
          when registering, so we know it&apos;s your account.
        </p>
      </div>
      <div>
        <label htmlFor={`${id}-new`} className="block text-sm font-medium text-ink">
          Correct email address
        </label>
        <input
          id={`${id}-new`}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={EMAIL_MAX}
          value={newEmail}
          onChange={(event) => setNewEmail(event.target.value)}
          className={cn(authControl, "mt-1.5 px-3.5")}
          {...errorProps(`${id}-new`, errors.newEmail)}
        />
        <ErrorText id={`${id}-new-error`} message={errors.newEmail} />
      </div>
      <div>
        <label htmlFor={`${id}-password`} className="block text-sm font-medium text-ink">
          Password
        </label>
        <div className="mt-1.5">
          <PasswordInput
            id={`${id}-password`}
            autoComplete="current-password"
            maxLength={PASSWORD_MAX}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            {...errorProps(`${id}-password`, errors.password)}
          />
        </div>
        <ErrorText id={`${id}-password-error`} message={errors.password} />
      </div>
      <NoticeBox notice={notice} />
      <div className="flex flex-col gap-3 sm:flex-row">
        <button type="submit" disabled={pending || !newEmail || !password} className={primaryButton}>
          {pending && <Spinner />}
          {pending ? "Saving…" : "Save and send link"}
        </button>
        <button type="button" onClick={onCancel} className={secondaryButton}>
          Cancel
        </button>
      </div>
    </form>
  );
}
