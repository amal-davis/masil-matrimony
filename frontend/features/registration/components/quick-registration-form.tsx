"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import type { CountryCode } from "libphonenumber-js";
import Link from "next/link";
import { useId, useState, useTransition } from "react";
import { useForm, useWatch } from "react-hook-form";

import {
  controlClasses,
  ErrorText,
  errorProps,
  Field,
  SegmentedOption,
  Select,
} from "@/components/ui/form-field";
import { cn } from "@/lib/utils";

import { registerMember, type RegisterField } from "@/features/auth/actions";
import { NoticeBox, Spinner, type Notice } from "@/features/auth/components/auth-ui";
import { MobileNumberInput } from "@/features/auth/components/mobile-number-input";
import { LOGIN_PATH } from "@/features/auth/constants";
import { DEFAULT_SMS_COUNTRY, EMAIL_MAX } from "@/features/auth/schema";
import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";

import {
  createdForOptions,
  genderOptions,
  quickRegistrationSchema,
  type QuickRegistrationInput,
  type QuickRegistrationValues,
} from "../schema";

/** Preselect gender when the relationship already implies it. */
const genderFor: Record<string, "male" | "female" | undefined> = { son: "male", daughter: "female" };

/** Form fields in page order, for focusing the first one the server rejected. */
const FIELD_ORDER: RegisterField[] = [
  "createdFor",
  "gender",
  "fullName",
  "dateOfBirth",
  "country",
  "mobile",
  "email",
  "acceptTerms",
];

/**
 * Registration form in the homepage hero. A Server Action checks the details
 * and sends a code by SMS to the mobile number, then opens the code screen
 * (/verify-mobile); the account and draft profile are created once the code is
 * verified. No password: members always sign in with an SMS code.
 */
export function QuickRegistrationForm({ className }: { className?: string }) {
  const id = useId();
  const [notice, setNotice] = useState<Notice>(null);
  // The number already has an account: offer to log in instead.
  const [phoneRegistered, setPhoneRegistered] = useState(false);
  const [pending, startTransition] = useTransition();
  const {
    register,
    handleSubmit,
    setValue,
    setError,
    setFocus,
    getValues,
    control,
    formState: { errors, isSubmitted },
  } = useForm<QuickRegistrationInput, unknown, QuickRegistrationValues>({
    resolver: zodResolver(quickRegistrationSchema),
    mode: "onTouched",
    defaultValues: { fullName: "", country: DEFAULT_SMS_COUNTRY, mobile: "", dateOfBirth: "", email: "" },
  });
  const country = useWatch({ control, name: "country" }) as CountryCode;

  const onSubmit = () => {
    if (pending) return;
    startTransition(async () => {
      setNotice(null);
      setPhoneRegistered(false);
      if (DASHBOARD_PREVIEW) {
        setNotice({ kind: "error", message: "Design preview: registration isn't available, and nothing was saved." });
        return;
      }
      // The raw input is sent; the Server Action validates it again. On success it redirects to /verify-mobile.
      const result = await registerMember(getValues());
      setPhoneRegistered(Boolean(result.phoneRegistered));
      const fieldErrors = result.fieldErrors ?? {};
      for (const field of FIELD_ORDER) {
        const message = fieldErrors[field];
        if (message) setError(field, { type: "server", message });
      }
      const first = FIELD_ORDER.find((field) => fieldErrors[field]);
      if (first && first !== "gender") setFocus(first);
      if (result.message) setNotice({ kind: "error", message: result.message });
    });
  };

  const fieldId = (name: string) => `${id}-${name}`;

  return (
    <div className={cn("rounded-xl bg-white p-5 shadow-[0_12px_32px_rgba(31,5,11,0.28)] sm:p-6", className)}>
      <h2 id={fieldId("title")} className="font-display text-2xl font-semibold text-ink sm:text-[1.75rem]">
        Create your free profile
      </h2>
      <p className="mt-1 text-[0.9375rem] text-ink-muted">
        Free and private. Already a member?{" "}
        <Link href="/login" className="font-medium text-wine-600 underline underline-offset-2">
          Sign in
        </Link>
      </p>

      <form
        noValidate
        aria-labelledby={fieldId("title")}
        onSubmit={handleSubmit(onSubmit)}
        aria-busy={pending}
        className="mt-4 flex flex-col gap-3"
      >
        <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
          <Field id={fieldId("createdFor")} label="Profile created for" error={errors.createdFor?.message}>
            <Select
              id={fieldId("createdFor")}
              defaultValue=""
              {...errorProps(fieldId("createdFor"), errors.createdFor?.message)}
              {...register("createdFor", {
                onChange: (event) => {
                  const gender = genderFor[event.target.value];
                  if (gender) setValue("gender", gender, { shouldValidate: isSubmitted });
                },
              })}
            >
              <option value="" disabled>
                Select
              </option>
              {createdForOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>

          <fieldset
            aria-describedby={errors.gender ? `${fieldId("gender")}-error` : undefined}
            className="min-w-0"
          >
            <legend className="text-sm font-medium text-ink">Gender</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              {genderOptions.map((option) => (
                <SegmentedOption
                  key={option.value}
                  value={option.value}
                  label={option.label}
                  invalid={Boolean(errors.gender)}
                  {...register("gender")}
                />
              ))}
            </div>
            <ErrorText id={`${fieldId("gender")}-error`} message={errors.gender?.message} />
          </fieldset>
        </div>

        <Field id={fieldId("fullName")} label="Full name" error={errors.fullName?.message}>
          <input
            id={fieldId("fullName")}
            type="text"
            autoComplete="name"
            className={controlClasses}
            {...errorProps(fieldId("fullName"), errors.fullName?.message)}
            {...register("fullName")}
          />
        </Field>

        {/* A date needs only half the row; the mobile number below gets the full width for its country picker. */}
        <div className="sm:w-1/2 sm:pr-2">
          <Field id={fieldId("dateOfBirth")} label="Date of birth" error={errors.dateOfBirth?.message}>
            <input
              id={fieldId("dateOfBirth")}
              type="date"
              autoComplete="bday"
              className={cn(controlClasses, "pr-2")}
              {...errorProps(fieldId("dateOfBirth"), errors.dateOfBirth?.message)}
              {...register("dateOfBirth")}
            />
          </Field>
        </div>

        <div>
          <MobileNumberInput
            id={fieldId("mobile")}
            country={country}
            onCountryChange={(code) => setValue("country", code, { shouldValidate: isSubmitted })}
            error={errors.mobile?.message}
            hint="We'll send a verification code to this number by SMS. You'll use it to log in."
            inputProps={register("mobile")}
          />
          {phoneRegistered && (
            <p className="mt-1.5 text-sm">
              <Link href={LOGIN_PATH} className="font-medium text-wine-600 underline underline-offset-2">
                Log in with this number
              </Link>
            </p>
          )}
        </div>

        <Field id={fieldId("email")} label="Email address" error={errors.email?.message}>
          <input
            id={fieldId("email")}
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={EMAIL_MAX}
            className={controlClasses}
            {...errorProps(fieldId("email"), errors.email?.message)}
            {...register("email")}
          />
        </Field>

        <div>
          <label className="flex items-start gap-3 text-sm text-ink-muted">
            <input
              type="checkbox"
              className="mt-0.5 size-5 shrink-0 accent-wine-600"
              {...errorProps(fieldId("acceptTerms"), errors.acceptTerms?.message)}
              {...register("acceptTerms")}
            />
            <span>
              I agree to the{" "}
              <Link href="/terms-and-conditions" className="font-medium text-wine-600 underline underline-offset-2">
                Terms of Use
              </Link>{" "}
              and{" "}
              <Link href="/privacy-policy" className="font-medium text-wine-600 underline underline-offset-2">
                Privacy Policy
              </Link>
              .
            </span>
          </label>
          <ErrorText id={`${fieldId("acceptTerms")}-error`} message={errors.acceptTerms?.message} />
        </div>

        <NoticeBox notice={notice} emptyOffset="-mt-3" />

        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-13 items-center justify-center gap-2.5 rounded-md bg-wine-600 px-6 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-wait disabled:opacity-60"
        >
          {pending && <Spinner />}
          {pending ? "Sending verification code…" : "Register free"}
        </button>
        <p className="-mt-2 text-sm leading-relaxed text-ink-muted">
          Next, enter the code we send to your mobile. Your account is created once it&apos;s verified.
        </p>

      </form>
    </div>
  );
}
