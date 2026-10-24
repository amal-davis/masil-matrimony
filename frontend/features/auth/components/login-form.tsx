"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState, useTransition } from "react";
import { useForm } from "react-hook-form";

import { ErrorText, errorProps } from "@/components/ui/form-field";
import { cn } from "@/lib/utils";

import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";

import { resendVerification, signIn } from "../actions";
import { FORGOT_PASSWORD_PATH, SIGNED_IN_COOKIE } from "../constants";
import { safeRedirectPath } from "../redirect";
import { EMAIL_MAX, loginSchema, PASSWORD_MAX, type LoginValues } from "../schema";
import { authControl, NoticeBox, PasswordInput, primaryButton, Spinner, textLink, type Notice } from "./auth-ui";

/**
 * Email and password sign-in. The password goes only to a Server Action
 * (never to browser storage), and tokens never reach the browser at all.
 */
export function LoginForm() {
  const id = useId();
  const router = useRouter();
  const fieldId = (name: string) => `${id}-${name}`;
  const [notice, setNotice] = useState<Notice>(null);
  // Right password, but the email isn't verified yet: offer a new link instead of the dashboard.
  const [unverified, setUnverified] = useState(false);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    // Arriving from a successful verification link.
    if (new URLSearchParams(window.location.search).get("verified") === "1") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setNotice({ kind: "info", message: "Your email has been verified. Sign in to continue to your account." });
    }
  }, []);

  const sendNewLink = () =>
    startTransition(async () => {
      const result = await resendVerification();
      setNotice({ kind: result.ok ? "info" : "error", message: result.message });
      if (result.ok) setUnverified(false);
    });

  const {
    register,
    handleSubmit,
    setFocus,
    setValue,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "", remember: false },
  });

  const onSubmit = (values: LoginValues) => {
    if (pending) return;
    startTransition(async () => {
      setNotice(null);
      // Only the `next` value is passed; the server checks it is a path on this site.
      const next = new URLSearchParams(window.location.search).get("next") ?? undefined;
      if (DASHBOARD_PREVIEW) {
        // Design preview: no account is signed in. The readable display flag only makes the
        // site header show "My Dashboard"; it grants nothing.
        document.cookie = `${SIGNED_IN_COOKIE}=1; path=/; max-age=86400; samesite=lax`;
        router.push(safeRedirectPath(next));
        return;
      }
      // On success the action redirects and this component unmounts.
      const result = await signIn(values, next);
      setUnverified(Boolean(result.unverified));
      setNotice({ kind: "error", message: result.message });
      setValue("password", "");
      setFocus("password");
    });
  };

  const emailError = errors.email?.message;
  const passwordError = errors.password?.message;

  return (
    <div>
      {DASHBOARD_PREVIEW && (
        <p className="mb-6 rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-[0.9375rem] text-ink">
          <strong className="font-semibold">Design preview.</strong> No real account is signed in. Enter any email
          address and password to open the sample member dashboard.
        </p>
      )}

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

        <div className="min-w-0">
          <label htmlFor={fieldId("password")} className="block text-sm font-medium text-ink">
            Password
          </label>
          <div className="mt-1.5">
            <PasswordInput
              id={fieldId("password")}
              autoComplete="current-password"
              maxLength={PASSWORD_MAX}
              required
              {...errorProps(fieldId("password"), passwordError)}
              {...register("password")}
            />
          </div>
          <ErrorText id={`${fieldId("password")}-error`} message={passwordError} />
        </div>

        <div className="-my-1 flex flex-wrap items-center justify-between gap-x-4">
          <label className="flex min-h-12 cursor-pointer items-center gap-3 text-[0.9375rem] text-ink">
            <input type="checkbox" className="size-5 shrink-0 accent-wine-600" {...register("remember")} />
            Keep me signed in
          </label>
          <Link href={FORGOT_PASSWORD_PATH} className={cn(textLink, "-mr-1")}>
            Forgot password?
          </Link>
        </div>

        <NoticeBox notice={notice} />

        {unverified && (
          <button
            type="button"
            onClick={sendNewLink}
            disabled={pending}
            className="-mt-1 inline-flex h-13 w-full items-center justify-center rounded-md border-[1.5px] border-wine-600 bg-white px-8 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-brand-50 focus-visible:outline-wine-600 disabled:opacity-60"
          >
            Send a new verification link
          </button>
        )}

        <button type="submit" disabled={pending} className={primaryButton}>
          {pending && <Spinner />}
          {pending ? "Signing in…" : "Sign In"}
        </button>

        <p className="-mt-1 text-sm leading-relaxed text-ink-muted">
          Only tick &ldquo;Keep me signed in&rdquo; on your own device. Otherwise you&apos;re signed out when you close
          the browser.
        </p>
      </form>
    </div>
  );
}
