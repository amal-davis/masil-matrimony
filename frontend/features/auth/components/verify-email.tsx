"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";

import { cn } from "@/lib/utils";

import { resendVerification, verifyEmail, type VerifyEmailResult } from "../actions";
import { CHECK_EMAIL_PATH, DEFAULT_AFTER_LOGIN, LOGIN_PATH } from "../constants";
import { EMAIL_MAX } from "../schema";
import { authControl, NoticeBox, primaryButton, Spinner, type Notice } from "./auth-ui";

type State = { kind: "verifying" } | { kind: "missing" } | { kind: "result"; result: VerifyEmailResult };

const linkButton =
  "inline-flex h-13 w-full items-center justify-center rounded-md bg-wine-600 px-8 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600";

/** Pause on the success message before opening the dashboard, so it can be read and announced. */
const REDIRECT_DELAY_MS = 1500;

/** The token from the emailed link's fragment (#token=…), which browsers never send to a server. */
function readToken(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("token");
}

function StatusIcon({ tone }: { tone: "success" | "warning" | "pending" }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-12 shrink-0 items-center justify-center rounded-full",
        tone === "success" && "bg-success/10 text-success",
        tone === "warning" && "bg-danger/10 text-danger",
        tone === "pending" && "bg-brand-50 text-wine-600",
      )}
    >
      {tone === "pending" ? (
        <Spinner />
      ) : tone === "success" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="size-6">
          <path d="m5 12.5 4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="size-6">
          <path d="M12 8v5m0 3.5v.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </span>
  );
}

function Outcome({
  tone,
  title,
  message,
  children,
}: {
  tone: "success" | "warning" | "pending";
  title: string;
  message: string;
  children?: React.ReactNode;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  // Move focus to each new outcome so screen readers announce it.
  useEffect(() => {
    if (tone !== "pending") heading.current?.focus();
  }, [tone, title]);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-4">
        <StatusIcon tone={tone} />
        <div className="min-w-0" aria-live="polite">
          <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
            {title}
          </h2>
          <p className="mt-2 text-[0.9375rem] leading-relaxed text-pretty text-ink-muted">{message}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

/** Ask for a new link from the result page, by email address (no other details needed). */
function RequestNewLink() {
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [pending, start] = useTransition();
  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        start(async () => {
          const result = await resendVerification(email.trim());
          setNotice({ kind: result.ok ? "info" : "error", message: result.message });
        });
      }}
      className="flex flex-col gap-4 border-t border-line pt-5"
    >
      <div>
        <label htmlFor="verify-resend-email" className="block text-sm font-medium text-ink">
          Email address you registered with
        </label>
        <input
          id="verify-resend-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={EMAIL_MAX}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={cn(authControl, "mt-1.5 px-3.5")}
        />
      </div>
      <NoticeBox notice={notice} emptyOffset="-mt-3" />
      <button type="submit" disabled={pending || !email.trim()} className={primaryButton}>
        {pending && <Spinner />}
        {pending ? "Sending…" : "Send a new verification link"}
      </button>
    </form>
  );
}

/**
 * Checks the emailed link's token with the backend and shows the result. The
 * token is read from the fragment, removed from the address bar and history at
 * once, and sent only to our own Server Action. A link that verifies the
 * account also signs the member in (session cookies set by the Server Action),
 * and the page opens the dashboard; a used or expired link signs nobody in.
 */
export function VerifyEmail() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "verifying" });
  const token = useRef<string | null>(null);
  const started = useRef(false);

  const check = useCallback(async () => {
    if (!token.current) return setState({ kind: "missing" });
    setState({ kind: "verifying" });
    setState({ kind: "result", result: await verifyEmail(token.current) });
  }, []);

  useEffect(() => {
    // Once only: the token leaves the address bar on the first run (and Strict Mode runs effects twice).
    if (started.current) return;
    started.current = true;
    token.current = readToken();
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    // The location is only known in the browser, never while prerendering.
    void check();
  }, [check]);

  const signedIn = state.kind === "result" && state.result.ok && state.result.signedIn;
  useEffect(() => {
    if (!signedIn) return;
    const timer = window.setTimeout(() => router.replace(DEFAULT_AFTER_LOGIN), REDIRECT_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [signedIn, router]);

  if (state.kind === "verifying") {
    return <Outcome tone="pending" title="Verifying your email…" message="This only takes a moment. Please keep this page open." />;
  }
  if (state.kind === "missing") {
    return (
      <Outcome
        tone="warning"
        title="This link is incomplete"
        message="Please open the link from your verification email again. If your email app split it across lines, copy the whole address into your browser."
      >
        <Link href={CHECK_EMAIL_PATH} className={linkButton}>
          Get a new link
        </Link>
      </Outcome>
    );
  }
  const { result } = state;
  if (result.ok) {
    return result.signedIn ? (
      <Outcome tone="success" title="Email verified" message={`${result.message} Taking you to your dashboard…`}>
        <Link href={DEFAULT_AFTER_LOGIN} replace className={linkButton}>
          Go to my dashboard
        </Link>
      </Outcome>
    ) : (
      <Outcome tone="success" title="Email verified" message={result.message}>
        <Link href={`${LOGIN_PATH}?verified=1`} className={linkButton}>
          Continue to sign in
        </Link>
      </Outcome>
    );
  }

  switch (result.reason) {
    case "used":
      return (
        <Outcome tone="success" title="Already verified" message={result.message}>
          <Link href={LOGIN_PATH} className={linkButton}>
            Sign in
          </Link>
        </Outcome>
      );
    case "expired":
      return (
        <Outcome tone="warning" title="This link has expired" message={result.message}>
          <RequestNewLink />
        </Outcome>
      );
    case "invalid":
      return (
        <Outcome tone="warning" title="This link can't be used" message={result.message}>
          <RequestNewLink />
        </Outcome>
      );
    default:
      return (
        <Outcome tone="warning" title="We couldn't verify your email" message={result.message}>
          <button type="button" onClick={() => void check()} className={primaryButton}>
            Try again
          </button>
        </Outcome>
      );
  }
}
