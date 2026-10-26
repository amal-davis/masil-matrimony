"use client";

import { useEffect, useId, useRef, useState, useTransition, type FormEvent, type ReactNode } from "react";

import { ErrorText } from "@/components/ui/form-field";
import { cn } from "@/lib/utils";

import type { PendingCode, SendCodeResult, VerifyCodeResult } from "../actions";
import { NoticeBox, primaryButton, Spinner, type Notice } from "./auth-ui";
import { OtpInput } from "./otp-input";

export const textButton =
  "inline-flex min-h-12 items-center rounded-sm px-1 text-[0.9375rem] font-medium text-wine-600 underline-offset-4 transition-colors hover:text-wine-800 hover:underline focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:text-ink-muted disabled:no-underline";

const formatWait = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/** Seconds left until `until` (a Date.now() timestamp), ticking every second. */
function useCountdown(until: number) {
  // The clock is only read in the browser, never while rendering on the server.
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    const update = () => {
      const seconds = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setLeft(seconds);
      return seconds;
    };
    if (update() === 0) return;
    const timer = window.setInterval(() => {
      if (update() === 0) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return left;
}

/**
 * Entering the code from the SMS: one field drawn as digit boxes (pasting the
 * whole code and SMS autofill work), the time left, "Resend code" after the
 * cooldown, and a way back to change the number. The parent supplies the
 * Server Actions; a correct code makes them redirect, so this only handles failures.
 */
export function OtpStep({
  pending,
  onPendingChange,
  verify,
  resend,
  onExpired,
  changeNumber,
  submitLabel,
  initialNotice = null,
}: {
  pending: PendingCode;
  onPendingChange: (pending: PendingCode) => void;
  verify: (code: string) => Promise<VerifyCodeResult>;
  resend: () => Promise<SendCodeResult>;
  /** The code (or registration) can't be resumed on this device: go back to the start. */
  onExpired: (message: string) => void;
  /** The "Change mobile number" control. */
  changeNumber: ReactNode;
  submitLabel: string;
  initialNotice?: Notice;
}) {
  const id = useId();
  const codeId = `${id}-code`;
  const codeRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string>();
  const [dead, setDead] = useState(false); // this code can't be used any more
  const [notice, setNotice] = useState<Notice>(initialNotice);
  const [sending, startSending] = useTransition();
  const [verifying, startVerifying] = useTransition();
  const resendIn = useCountdown(pending.resendAt);
  const expiresIn = useCountdown(pending.expiresAt);
  const expired = expiresIn === 0;

  useEffect(() => {
    codeRef.current?.focus();
  }, [pending]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (verifying || dead || expired) return;
    if (code.length !== pending.codeLength) {
      setCodeError(`Enter all ${pending.codeLength} digits of the code.`);
      codeRef.current?.focus();
      return;
    }
    startVerifying(async () => {
      setNotice(null);
      setCodeError(undefined);
      // On success the action redirects and this component unmounts.
      const result = await verify(code);
      if (result.reason === "incorrect") {
        const left =
          result.attemptsRemaining !== undefined
            ? ` ${result.attemptsRemaining} ${result.attemptsRemaining === 1 ? "attempt" : "attempts"} left.`
            : "";
        setCodeError(`${result.message}${left}`);
        setCode("");
        codeRef.current?.focus();
      } else if (result.reason === "error") {
        setNotice({ kind: "error", message: result.message });
      } else if (result.reason === "conflict") {
        onExpired(result.message);
      } else {
        setDead(true);
        setCode("");
        setNotice({ kind: "error", message: result.message });
      }
    });
  };

  const onResend = () =>
    startSending(async () => {
      setNotice(null);
      const result = await resend();
      if (!result.ok) {
        if (result.expired) {
          onExpired(result.message);
          return;
        }
        if (result.retryAfter) {
          onPendingChange({ ...pending, resendAt: Date.now() + result.retryAfter * 1000 });
        }
        setNotice({ kind: "error", message: result.message });
        return;
      }
      setCode("");
      setCodeError(undefined);
      setDead(false);
      onPendingChange(result.pending);
      setNotice({ kind: "info", message: `A new code has been sent to ${result.pending.maskedPhone}. Earlier codes no longer work.` });
    });

  const unusable = dead || expired;

  return (
    <div>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-mist px-4 py-3 text-[0.9375rem] text-ink">
        <span className="text-ink-muted">Code sent by SMS to</span>
        <span className="font-semibold tracking-wide whitespace-nowrap tabular-nums">{pending.maskedPhone}</span>
      </p>

      <form noValidate onSubmit={onSubmit} aria-busy={verifying} className="mt-6 flex flex-col gap-5">
        <div>
          <label htmlFor={codeId} className="block text-sm font-medium text-ink">
            Verification code
          </label>
          <OtpInput
            id={codeId}
            inputRef={codeRef}
            length={pending.codeLength}
            value={code}
            onChange={(value) => {
              setCode(value);
              if (codeError) setCodeError(undefined);
            }}
            disabled={unusable || verifying}
            required
            aria-invalid={codeError ? true : undefined}
            aria-describedby={cn(`${codeId}-hint`, codeError && `${codeId}-error`)}
            className="mt-1.5"
          />
          <ErrorText id={`${codeId}-error`} message={codeError} />
          <p role="status" className="sr-only">
            {expired ? "The code has expired. Request a new code." : ""}
          </p>
          {/* Not a live region: it ticks every second. Expiry is announced once, below. */}
          <p id={`${codeId}-hint`} className="mt-2 text-sm leading-relaxed text-ink-muted">
            {expiresIn === null
              ? `Enter the ${pending.codeLength}-digit code from the SMS.`
              : expired
                ? "This code has expired. Request a new code below."
                : `Enter the ${pending.codeLength}-digit code from the SMS. It expires in ${formatWait(expiresIn)}.`}
          </p>
        </div>

        <NoticeBox notice={notice} />

        <button type="submit" disabled={verifying || unusable} className={primaryButton}>
          {verifying && <Spinner />}
          {verifying ? "Verifying…" : submitLabel}
        </button>

        <div className="-mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <button
            type="button"
            onClick={onResend}
            disabled={sending || verifying || resendIn === null || resendIn > 0}
            className={textButton}
          >
            {sending ? "Sending…" : "Resend code"}
            {!sending && resendIn !== null && resendIn > 0 && (
              <span className="ml-1.5 font-normal tabular-nums">
                <span className="sr-only">available </span>in {formatWait(resendIn)}
              </span>
            )}
          </button>
          {changeNumber}
        </div>
      </form>
    </div>
  );
}
