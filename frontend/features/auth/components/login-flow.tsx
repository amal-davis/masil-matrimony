"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useRef, useState, useTransition, type FormEvent, type ReactNode } from "react";
import { useForm } from "react-hook-form";

import { controlClasses, ErrorText } from "@/components/ui/form-field";
import { PhoneIcon, ShieldCheckIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import { requestLoginCode, verifyLoginCode, type VerifyFailure } from "../actions";
import {
  loginPhoneSchema,
  maskPhoneNumber,
  PHONE_INPUT_MAX,
  type LoginPhoneInput,
  type LoginPhoneValues,
} from "../schema";
import { OtpInput } from "./otp-input";

type Challenge = {
  challengeId: string;
  phoneNumber: string;
  codeLength: number;
  expiresIn: number;
};

type Notice = { kind: "error" | "info"; message: string } | null;

// Flags are static files in public/flags; plain <img> paths don't get a base path added automatically.
const FLAG_BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const primaryButton =
  "inline-flex h-13 w-full items-center justify-center gap-2.5 rounded-md bg-wine-600 px-8 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:opacity-60";

const textButton =
  "inline-flex min-h-12 items-center rounded-sm px-1 text-[0.9375rem] font-medium text-wine-600 underline-offset-4 transition-colors hover:text-wine-800 hover:underline focus-visible:outline-wine-600 disabled:cursor-not-allowed disabled:text-ink-muted disabled:no-underline";

function Spinner() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="size-5 motion-safe:animate-spin">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function StepHeading({ id, icon, title, children }: { id: string; icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-4">
      {/* Decorative; dropped on narrow phones so the heading and text get the full width. */}
      <span
        aria-hidden="true"
        className="hidden size-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-wine-600 sm:flex"
      >
        {icon}
      </span>
      <div className="min-w-0">
        <h2 id={id} className="text-xl font-semibold sm:text-[1.375rem]">
          {title}
        </h2>
        <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-pretty text-ink-muted">{children}</p>
      </div>
    </div>
  );
}

function NoticeBox({ notice }: { notice: Notice }) {
  return (
    <>
      <div role="alert" aria-live="assertive">
        {notice?.kind === "error" && (
          <p className="flex items-start gap-2.5 rounded-md border border-danger/40 bg-danger/5 px-4 py-3 text-[0.9375rem] text-ink">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-danger">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.5a.75.75 0 0 0-1.5 0v4a.75.75 0 0 0 1.5 0v-4ZM10 14.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="min-w-0">{notice.message}</span>
          </p>
        )}
      </div>
      <div role="status" aria-live="polite">
        {notice?.kind === "info" && (
          <p className="flex items-start gap-2.5 rounded-md border border-success/40 bg-success/5 px-4 py-3 text-[0.9375rem] text-ink">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-success">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.86-9.81a.75.75 0 0 0-1.22-.88l-3.24 4.5-1.6-1.6a.75.75 0 1 0-1.06 1.06l2.22 2.22a.75.75 0 0 0 1.14-.09l3.76-5.21Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="min-w-0">{notice.message}</span>
          </p>
        )}
      </div>
    </>
  );
}

const formatWait = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/** Seconds left until `until` (a Date.now() timestamp), ticking every second. */
function useCountdown(until: number) {
  // The clock is only read in the browser, never while prerendering the page.
  const [left, setLeft] = useState(0);
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
 * Two-step SMS login: mobile number, then the one-time code. The code and
 * tokens never touch browser storage; the challenge id lives only in memory.
 */
export function LoginFlow() {
  const id = useId();
  const fieldId = (name: string) => `${id}-${name}`;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string>();
  const [dead, setDead] = useState(false); // the current code can't be used any more
  const [notice, setNotice] = useState<Notice>(null);
  const [resendAt, setResendAt] = useState(0);
  const [sending, startSending] = useTransition();
  const [verifying, startVerifying] = useTransition();
  const resendIn = useCountdown(resendAt);

  const codeRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors },
  } = useForm<LoginPhoneInput, unknown, LoginPhoneValues>({
    resolver: zodResolver(loginPhoneSchema),
    mode: "onTouched",
    defaultValues: { phone: "" },
  });

  // Move focus to the field that matters on each step.
  useEffect(() => {
    if (challenge) codeRef.current?.focus();
  }, [challenge]);

  const sendCode = (phoneNumber: string, resend: boolean) =>
    startSending(async () => {
      setNotice(null);
      const result = await requestLoginCode(phoneNumber);
      if (!result.ok) {
        if (result.retryAfter) setResendAt(Date.now() + result.retryAfter * 1000);
        if (result.field === "phone" && !resend) {
          setError("phone", { type: "server", message: result.message });
          setFocus("phone");
        } else {
          setNotice({ kind: "error", message: result.message });
        }
        return;
      }
      setChallenge({
        challengeId: result.challengeId,
        phoneNumber,
        codeLength: result.codeLength,
        expiresIn: result.expiresIn,
      });
      setResendAt(Date.now() + result.resendAfter * 1000);
      setCode("");
      setCodeError(undefined);
      setDead(false);
      // The new challenge also moves focus back to the code field (see the effect above).
      if (resend) {
        setNotice({ kind: "info", message: "A new code has been requested. Any earlier code no longer works." });
      }
    });

  const onPhoneSubmit = ({ phoneNumber }: LoginPhoneValues) => {
    if (sending) return;
    sendCode(phoneNumber, false);
  };

  const onCodeSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!challenge || verifying || dead) return;
    if (code.length !== challenge.codeLength) {
      setCodeError(`Enter all ${challenge.codeLength} digits of the code.`);
      codeRef.current?.focus();
      return;
    }
    startVerifying(async () => {
      setNotice(null);
      setCodeError(undefined);
      // Only the `next` value is passed; the server checks it is a path on this site.
      const next = new URLSearchParams(window.location.search).get("next") ?? undefined;
      // On success the action redirects and this component unmounts.
      const result = await verifyLoginCode(challenge.challengeId, code, next);
      handleVerifyFailure(result.reason, result.message, result.attemptsRemaining);
    });
  };

  const handleVerifyFailure = (reason: VerifyFailure, message: string, attemptsRemaining?: number) => {
    if (reason === "incorrect") {
      const left =
        attemptsRemaining !== undefined
          ? ` ${attemptsRemaining} ${attemptsRemaining === 1 ? "attempt" : "attempts"} left.`
          : "";
      setCodeError(`${message}${left}`);
      setCode("");
      codeRef.current?.focus();
    } else if (reason === "error") {
      setNotice({ kind: "error", message });
    } else {
      setDead(true);
      setCode("");
      setNotice({ kind: "error", message });
    }
  };

  const changeNumber = () => {
    setChallenge(null);
    setNotice(null);
    setCode("");
    setCodeError(undefined);
    // The number stays in the form; put the cursor back in it once it is visible.
    requestAnimationFrame(() => setFocus("phone"));
  };

  const phoneError = errors.phone?.message;

  return (
    <div>
      {/* Step 1. Kept mounted (just hidden) on step 2 so the number is still there on "Change Mobile Number". */}
      <section aria-labelledby={fieldId("phone-title")} hidden={challenge !== null}>
        <StepHeading id={fieldId("phone-title")} icon={<PhoneIcon className="size-5" />} title="Login with Mobile Number">
          We&apos;ll send a one-time verification code to your mobile number by SMS.
        </StepHeading>

        <form noValidate onSubmit={handleSubmit(onPhoneSubmit)} className="mt-6 flex flex-col gap-5">
          <div className="min-w-0">
            <label htmlFor={fieldId("phone")} className="block text-sm font-medium text-ink">
              Mobile Number
            </label>
            {/* India only: a fixed +91 prefix joined to the field, not a country picker. */}
            <div className="mt-1.5 flex">
              <span
                id={`${fieldId("phone")}-prefix`}
                className="inline-flex h-13 shrink-0 items-center gap-2 rounded-l-md border border-r-0 border-field-line bg-mist px-3 text-base text-ink tabular-nums sm:text-lg"
              >
                {/* An SVG flag needs no optimisation, so next/image would add nothing here. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${FLAG_BASE_PATH}/flags/IN.svg`}
                  alt=""
                  width={24}
                  height={16}
                  className="h-4 w-6 rounded-[2px] object-cover ring-1 ring-ink/10"
                />
                <span className="sr-only">India country code </span>
                +91
              </span>
              <input
                id={fieldId("phone")}
                type="tel"
                inputMode="tel"
                autoComplete="tel-national"
                placeholder="Enter your mobile number"
                maxLength={PHONE_INPUT_MAX}
                required
                className={cn(controlClasses, "h-13 rounded-l-none sm:text-lg sm:tracking-wide")}
                aria-invalid={phoneError ? true : undefined}
                aria-describedby={cn(`${fieldId("phone")}-prefix`, phoneError && `${fieldId("phone")}-error`)}
                {...register("phone")}
              />
            </div>
            <ErrorText id={`${fieldId("phone")}-error`} message={phoneError} />
          </div>

          <button type="submit" disabled={sending} className={primaryButton}>
            {sending && <Spinner />}
            {sending ? "Sending OTP…" : "Send OTP"}
          </button>
        </form>
      </section>

      {/* Step 2 */}
      {challenge && (
        <section aria-labelledby={fieldId("code-title")}>
          <StepHeading
            id={fieldId("code-title")}
            icon={<ShieldCheckIcon className="size-5" />}
            title="Verify Your Mobile Number"
          >
            Enter the verification code sent by SMS to your registered mobile number.
          </StepHeading>

          <p className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-mist px-4 py-3 text-[0.9375rem] text-ink">
            <span className="text-ink-muted">Code requested for</span>
            <span className="font-semibold tracking-wide whitespace-nowrap tabular-nums">
              {maskPhoneNumber(challenge.phoneNumber)}
            </span>
          </p>

          <form noValidate onSubmit={onCodeSubmit} className="mt-6 flex flex-col gap-5">
            <div>
              <label htmlFor={fieldId("code")} className="block text-sm font-medium text-ink">
                Verification Code
              </label>
              <OtpInput
                id={fieldId("code")}
                inputRef={codeRef}
                length={challenge.codeLength}
                value={code}
                onChange={(value) => {
                  setCode(value);
                  if (codeError) setCodeError(undefined);
                }}
                disabled={dead || verifying}
                required
                aria-invalid={codeError ? true : undefined}
                aria-describedby={cn(`${fieldId("code")}-hint`, codeError && `${fieldId("code")}-error`)}
                className="mt-1.5"
              />
              <ErrorText id={`${fieldId("code")}-error`} message={codeError} />
              <p id={`${fieldId("code")}-hint`} className="mt-2 text-sm leading-relaxed text-ink-muted">
                The code is valid for {Math.round(challenge.expiresIn / 60)} minutes. If it doesn&apos;t arrive,
                check that this is the number registered with us.
              </p>
            </div>

            <NoticeBox notice={notice} />

            <button type="submit" disabled={verifying || dead} className={primaryButton}>
              {verifying && <Spinner />}
              {verifying ? "Verifying…" : "Verify & Login"}
            </button>

            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
              <button
                type="button"
                onClick={() => sendCode(challenge.phoneNumber, true)}
                disabled={sending || verifying || resendIn > 0}
                className={textButton}
              >
                {sending ? "Sending…" : "Resend OTP"}
                {resendIn > 0 && !sending && (
                  <span className="ml-1.5 font-normal tabular-nums">
                    in {formatWait(resendIn)}
                  </span>
                )}
              </button>
              <button type="button" onClick={changeNumber} disabled={verifying} className={textButton}>
                Change Mobile Number
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Errors from sending the first code show under step 1. */}
      {!challenge && notice && (
        <div className="mt-5">
          <NoticeBox notice={notice} />
        </div>
      )}
    </div>
  );
}
