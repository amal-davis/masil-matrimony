"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import { useForm } from "react-hook-form";

import { ErrorText, errorProps } from "@/components/ui/form-field";
import { MailIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";

import { requestPasswordReset } from "../actions";
import { EMAIL_MAX, forgotPasswordSchema, type ForgotPasswordValues } from "../schema";
import { authControl, NoticeBox, primaryButton, Spinner, textLink, type Notice } from "./auth-ui";

/** Shown after a request; its heading takes focus so screen readers announce the outcome. */
function LinkSent({ email, onTryAgain }: { email: string; onTryAgain: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start gap-4 rounded-md border border-success/40 bg-success/5 p-5">
        <MailIcon className="mt-0.5 hidden size-6 shrink-0 text-success sm:block" />
        <div className="min-w-0">
          <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold outline-none">
            Check your email
          </h2>
          <p className="mt-2 text-[0.9375rem] leading-relaxed text-pretty text-ink">
            If an account uses <strong className="font-semibold break-all">{email}</strong>, we&apos;ve sent it a link
            to set a new password. The link works once and expires after a short time.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Nothing after a few minutes? Check your spam folder, and that this is the email address on your account.
          </p>
        </div>
      </div>
      <div>
        <button type="button" onClick={onTryAgain} className={cn(textLink, "-ml-1")}>
          Use a different email address
        </button>
      </div>
    </div>
  );
}

/**
 * Request a password-reset link. The confirmation is worded the same whether
 * or not the address is registered, as the API's response is.
 */
export function ForgotPasswordForm() {
  const id = useId();
  const fieldId = (name: string) => `${id}-${name}`;
  const [notice, setNotice] = useState<Notice>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    mode: "onTouched",
    defaultValues: { email: "" },
  });

  const onSubmit = ({ email }: ForgotPasswordValues) => {
    if (pending) return;
    startTransition(async () => {
      setNotice(null);
      if (DASHBOARD_PREVIEW) {
        setNotice({ kind: "error", message: "Design preview: password reset isn't available, and no email is sent." });
        return;
      }
      const result = await requestPasswordReset(email);
      if (!result.ok) {
        setNotice({ kind: "error", message: result.message });
        return;
      }
      setSentTo(email);
    });
  };

  const tryAgain = () => {
    setSentTo(null);
    requestAnimationFrame(() => setFocus("email"));
  };

  if (sentTo) return <LinkSent email={sentTo} onTryAgain={tryAgain} />;

  const emailError = errors.email?.message;

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} aria-busy={pending} className="flex flex-col gap-5">
      <div className="min-w-0">
        <label htmlFor={fieldId("email")} className="block text-sm font-medium text-ink">
          Email Address
        </label>
        <input
          id={fieldId("email")}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="name@example.com"
          maxLength={EMAIL_MAX}
          required
          className={cn(authControl, "mt-1.5 px-3.5")}
          {...errorProps(fieldId("email"), emailError)}
          {...register("email")}
        />
        <ErrorText id={`${fieldId("email")}-error`} message={emailError} />
      </div>

      <NoticeBox notice={notice} />

      <button type="submit" disabled={pending} className={primaryButton}>
        {pending && <Spinner />}
        {pending ? "Sending link…" : "Send Reset Link"}
      </button>
    </form>
  );
}
