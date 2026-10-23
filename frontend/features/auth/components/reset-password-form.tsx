"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import { useForm } from "react-hook-form";

import { ErrorText, errorProps } from "@/components/ui/form-field";

import { resetPassword } from "../actions";
import { FORGOT_PASSWORD_PATH, LOGIN_PATH } from "../constants";
import { PASSWORD_MAX, PASSWORD_MIN, resetPasswordSchema, type ResetPasswordValues } from "../schema";
import { NoticeBox, PasswordInput, primaryButton, Spinner, type Notice } from "./auth-ui";

type ResetLink = { uid: string; token: string };

/**
 * The uid and token from the emailed link's fragment (#uid=…&token=…). The
 * fragment is never sent to a server, so the token stays out of access logs.
 */
function readLink(): ResetLink | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const uid = params.get("uid");
  const token = params.get("token");
  return uid && token ? { uid, token } : null;
}

const linkButton =
  "inline-flex h-13 w-full items-center justify-center rounded-md bg-wine-600 px-8 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600";

function Outcome({ title, children, href, action }: { title: string; children: string; href: string; action: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
          {title}
        </h2>
        <p className="mt-2 text-[0.9375rem] leading-relaxed text-pretty text-ink-muted">{children}</p>
      </div>
      <Link href={href} className={linkButton}>
        {action}
      </Link>
    </div>
  );
}

/** Choose a new password from an emailed reset link. */
export function ResetPasswordForm() {
  const id = useId();
  const fieldId = (name: string) => `${id}-${name}`;
  // undefined until the fragment has been read in the browser.
  const [link, setLink] = useState<ResetLink | null | undefined>(undefined);
  const [linkDead, setLinkDead] = useState(false);
  const [done, setDone] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [pending, startTransition] = useTransition();

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    mode: "onTouched",
    defaultValues: { password: "", confirm: "" },
  });

  useEffect(() => {
    // The location is only known in the browser, never while prerendering.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLink(readLink());
    // Drop the token from the address bar and history; it stays in memory only.
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }, []);

  const onSubmit = ({ password, confirm }: ResetPasswordValues) => {
    if (pending || !link) return;
    startTransition(async () => {
      setNotice(null);
      const result = await resetPassword(link.uid, link.token, password, confirm);
      if (result.ok) {
        setDone(true);
      } else if (result.reason === "link") {
        setLinkDead(true);
      } else if (result.reason === "password") {
        setError(result.field, { type: "server", message: result.message });
        setFocus(result.field);
      } else {
        setNotice({ kind: "error", message: result.message });
      }
    });
  };

  if (link === undefined) {
    return <p className="text-[0.9375rem] text-ink-muted">Checking your link…</p>;
  }

  if (done) {
    return (
      <Outcome title="Your password has been set" href={LOGIN_PATH} action="Sign In">
        You can now sign in with your email address and new password. For your security, you&apos;ve been signed out
        on any other devices.
      </Outcome>
    );
  }

  if (!link || linkDead) {
    return (
      <Outcome title="This link can't be used" href={FORGOT_PASSWORD_PATH} action="Request a New Link">
        Password reset links work once, expire after a short time, and stop working once you sign in. Request a new
        link and use the newest email we send you.
      </Outcome>
    );
  }

  const passwordError = errors.password?.message;
  const confirmError = errors.confirm?.message;

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} aria-busy={pending} className="flex flex-col gap-5">
      <div className="min-w-0">
        <label htmlFor={fieldId("password")} className="block text-sm font-medium text-ink">
          New Password
        </label>
        <div className="mt-1.5">
          <PasswordInput
            id={fieldId("password")}
            autoComplete="new-password"
            maxLength={PASSWORD_MAX}
            required
            {...errorProps(fieldId("password"), passwordError)}
            aria-describedby={[`${fieldId("password")}-hint`, passwordError && `${fieldId("password")}-error`]
              .filter(Boolean)
              .join(" ")}
            {...register("password")}
          />
        </div>
        <ErrorText id={`${fieldId("password")}-error`} message={passwordError} />
        <p id={`${fieldId("password")}-hint`} className="mt-1.5 text-sm leading-relaxed text-ink-muted">
          At least {PASSWORD_MIN} characters. Avoid common words and anything like your name or email address.
        </p>
      </div>

      <div className="min-w-0">
        <label htmlFor={fieldId("confirm")} className="block text-sm font-medium text-ink">
          Confirm New Password
        </label>
        <div className="mt-1.5">
          <PasswordInput
            id={fieldId("confirm")}
            autoComplete="new-password"
            maxLength={PASSWORD_MAX}
            required
            {...errorProps(fieldId("confirm"), confirmError)}
            {...register("confirm")}
          />
        </div>
        <ErrorText id={`${fieldId("confirm")}-error`} message={confirmError} />
      </div>

      <NoticeBox notice={notice} />

      <button type="submit" disabled={pending} className={primaryButton}>
        {pending && <Spinner />}
        {pending ? "Saving…" : "Set New Password"}
      </button>
    </form>
  );
}
