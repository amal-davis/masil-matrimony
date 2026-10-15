"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import {
  controlClasses,
  ErrorText,
  errorProps,
  Field,
  SegmentedOption,
  Select,
} from "@/components/ui/form-field";
import { cn } from "@/lib/utils";

import {
  createdForOptions,
  genderOptions,
  quickRegistrationSchema,
  type QuickRegistrationInput,
  type QuickRegistrationValues,
} from "../schema";

type Status = "idle" | "unavailable";

/** Preselect gender when the relationship already implies it. */
const genderFor: Record<string, "male" | "female" | undefined> = { son: "male", daughter: "female" };

/**
 * Compact first step of registration shown in the homepage hero.
 *
 * The registration API (POST /auth/register/ + OTP) is planned but not built,
 * so a valid submission is NOT sent anywhere: the form says so plainly instead
 * of pretending to succeed. Wire `onSubmit` to the API when it exists.
 */
export function QuickRegistrationForm({ className }: { className?: string }) {
  const id = useId();
  const [status, setStatus] = useState<Status>("idle");
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting, isSubmitted },
  } = useForm<QuickRegistrationInput, unknown, QuickRegistrationValues>({
    resolver: zodResolver(quickRegistrationSchema),
    mode: "onTouched",
    defaultValues: { fullName: "", mobile: "", dateOfBirth: "" },
  });

  const onSubmit = async () => {
    // TODO: POST /auth/register/ (see docs/api-specification.md) and continue to OTP verification.
    setStatus("unavailable");
  };

  const fieldId = (name: string) => `${id}-${name}`;

  return (
    <div className={cn("rounded-xl bg-white p-5 shadow-[0_12px_32px_rgba(31,5,11,0.28)] sm:p-7", className)}>
      <h2 id={fieldId("title")} className="font-display text-2xl font-semibold text-ink sm:text-[1.75rem]">
        Create your free profile
      </h2>
      <p className="mt-1 text-[0.9375rem] text-ink-muted">
        Takes a minute. Your details stay private until you choose to share them.
      </p>

      <form
        noValidate
        aria-labelledby={fieldId("title")}
        onSubmit={handleSubmit(onSubmit)}
        onChange={() => status !== "idle" && setStatus("idle")}
        className="mt-5 flex flex-col gap-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
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

        <div className="grid gap-4 sm:grid-cols-2">
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

          <Field id={fieldId("mobile")} label="Mobile number" error={errors.mobile?.message}>
            <div className="flex min-w-0">
              <span
                aria-hidden="true"
                className="inline-flex h-12 shrink-0 items-center rounded-l-md border border-r-0 border-field-line bg-surface-muted px-3 text-base text-ink-muted"
              >
                +91
              </span>
              <input
                id={fieldId("mobile")}
                type="tel"
                inputMode="numeric"
                autoComplete="tel-national"
                maxLength={12}
                className={cn(controlClasses, "rounded-l-none")}
                aria-invalid={errors.mobile ? true : undefined}
                aria-describedby={cn(
                  `${fieldId("mobile")}-hint`,
                  errors.mobile && `${fieldId("mobile")}-error`,
                )}
                {...register("mobile")}
              />
            </div>
            <span id={`${fieldId("mobile")}-hint`} className="sr-only">
              Indian mobile number, 10 digits, country code +91
            </span>
          </Field>
        </div>

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
              <Link href="/terms" className="font-medium text-wine-600 underline underline-offset-2">
                Terms of Use
              </Link>{" "}
              and{" "}
              <Link href="/privacy" className="font-medium text-wine-600 underline underline-offset-2">
                Privacy Policy
              </Link>
              .
            </span>
          </label>
          <ErrorText id={`${fieldId("acceptTerms")}-error`} message={errors.acceptTerms?.message} />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-13 items-center justify-center rounded-md bg-wine-600 px-6 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-wait disabled:opacity-60"
        >
          {isSubmitting ? "Please wait…" : "Register free"}
        </button>

        <div role="status" aria-live="polite">
          {status === "unavailable" && (
            <p className="rounded-md border border-accent-400 bg-accent-100 px-4 py-3 text-sm text-ink">
              <strong className="font-semibold">Online registration isn&rsquo;t open yet.</strong> Your
              details have not been sent or saved. Please check back soon.
            </p>
          )}
        </div>
      </form>
    </div>
  );
}
