"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import type { CountryCode } from "libphonenumber-js";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition, type ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";

import { PhoneIcon, ShieldCheckIcon } from "@/components/ui/icons";

import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";

import {
  cancelPendingCode,
  requestLoginCode,
  resendLoginCode,
  verifyLoginCode,
  type PendingCode,
} from "../actions";
import { SIGNED_IN_COOKIE } from "../constants";
import { safeRedirectPath } from "../redirect";
import { DEFAULT_SMS_COUNTRY, loginPhoneSchema, type LoginPhoneInput, type LoginPhoneValues } from "../schema";
import { NoticeBox, primaryButton, Spinner, type Notice } from "./auth-ui";
import { MobileNumberInput } from "./mobile-number-input";
import { OtpStep, textButton } from "./otp-step";

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

/**
 * Two-step SMS sign-in: mobile number, then the one-time code. The code and
 * tokens never touch browser storage; the challenge id stays in an HTTP-only
 * cookie, so `initialPending` resumes the code step after a page refresh.
 */
export function LoginForm({ initialPending }: { initialPending?: PendingCode }) {
  const id = useId();
  const router = useRouter();
  const fieldId = (name: string) => `${id}-${name}`;
  const [pending, setPending] = useState<PendingCode | undefined>(initialPending);
  const [notice, setNotice] = useState<Notice>(null);
  const [sending, startSending] = useTransition();

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    setValue,
    getValues,
    control,
    formState: { errors },
  } = useForm<LoginPhoneInput, unknown, LoginPhoneValues>({
    resolver: zodResolver(loginPhoneSchema),
    mode: "onTouched",
    defaultValues: { country: DEFAULT_SMS_COUNTRY, phone: "", remember: false },
  });
  const country = useWatch({ control, name: "country" }) as CountryCode;

  const next = () => new URLSearchParams(window.location.search).get("next") ?? undefined;

  const onPhoneSubmit = () => {
    if (sending) return;
    startSending(async () => {
      setNotice(null);
      if (DASHBOARD_PREVIEW) {
        // Design preview: nothing is sent and no account is signed in. The readable display
        // flag only makes the site header show "My Dashboard"; it grants nothing.
        document.cookie = `${SIGNED_IN_COOKIE}=1; path=/; max-age=86400; samesite=lax`;
        router.push(safeRedirectPath(next()));
        return;
      }
      // The raw input is sent; the Server Action validates it again.
      const result = await requestLoginCode(getValues());
      if (!result.ok) {
        if (result.field === "phone") {
          setError("phone", { type: "server", message: result.message });
          setFocus("phone");
        } else {
          setNotice({ kind: "error", message: result.message });
        }
        return;
      }
      setPending(result.pending);
    });
  };

  const backToNumber = (message?: string) => {
    setPending(undefined);
    setNotice(message ? { kind: "error", message } : null);
    void cancelPendingCode();
    // Put the cursor back in the number once it is visible.
    requestAnimationFrame(() => setFocus("phone"));
  };

  if (pending) {
    return (
      <section aria-labelledby={fieldId("code-title")}>
        <StepHeading id={fieldId("code-title")} icon={<ShieldCheckIcon className="size-5" />} title="Enter your code">
          We&apos;ve sent a one-time code by SMS. If this number is registered with us, it arrives within a minute.
        </StepHeading>
        <div className="mt-6">
          <OtpStep
            pending={pending}
            onPendingChange={setPending}
            verify={(code) => verifyLoginCode(code, next())}
            resend={resendLoginCode}
            onExpired={backToNumber}
            submitLabel="Verify & log in"
            changeNumber={
              <button type="button" onClick={() => backToNumber()} className={textButton}>
                Change mobile number
              </button>
            }
          />
        </div>
      </section>
    );
  }

  const phoneError = errors.phone?.message;

  return (
    <section aria-labelledby={fieldId("phone-title")}>
      {DASHBOARD_PREVIEW && (
        <p className="mb-6 rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-[0.9375rem] text-ink">
          <strong className="font-semibold">Design preview.</strong> No SMS is sent and no real account is signed in.
          Enter any valid mobile number to open the sample member dashboard.
        </p>
      )}
      <StepHeading id={fieldId("phone-title")} icon={<PhoneIcon className="size-5" />} title="Log in with your mobile number">
        We&apos;ll send a one-time verification code to your registered mobile number by SMS.
      </StepHeading>

      <form noValidate onSubmit={handleSubmit(onPhoneSubmit)} aria-busy={sending} className="mt-6 flex flex-col gap-5">
        <MobileNumberInput
          id={fieldId("phone")}
          label="Mobile number"
          tall
          country={country}
          onCountryChange={(code) => setValue("country", code, { shouldValidate: Boolean(errors.phone) })}
          error={phoneError}
          inputProps={{ required: true, ...register("phone") }}
        />

        <label className="-my-1 flex min-h-12 cursor-pointer items-center gap-3 text-[0.9375rem] text-ink">
          <input type="checkbox" className="size-5 shrink-0 accent-wine-600" {...register("remember")} />
          Keep me signed in
        </label>

        <NoticeBox notice={notice} />

        <button type="submit" disabled={sending} className={primaryButton}>
          {sending && <Spinner />}
          {sending ? "Sending code…" : "Send code"}
        </button>

        <p className="-mt-1 text-sm leading-relaxed text-ink-muted">
          Only tick &ldquo;Keep me signed in&rdquo; on your own device. Otherwise you&apos;re signed out when you close
          the browser.
        </p>
      </form>
    </section>
  );
}
