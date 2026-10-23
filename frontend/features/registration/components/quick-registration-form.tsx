"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useId, useState, useTransition } from "react";
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

import { registerMember, type RegisterField } from "@/features/auth/actions";
import { NoticeBox, PasswordInput, Spinner, type Notice } from "@/features/auth/components/auth-ui";
import { EMAIL_MAX, PASSWORD_MAX, PASSWORD_MIN } from "@/features/auth/schema";
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
  "mobile",
  "email",
  "password",
  "acceptTerms",
];

/**
 * Registration form in the homepage hero. Creates the account (email and one
 * password, with show/hide instead of a confirmation box) and a draft profile
 * through a Server Action, signs the new member in and opens their profile to finish.
 */
export function QuickRegistrationForm({ className }: { className?: string }) {
  const id = useId();
  const [notice, setNotice] = useState<Notice>(null);
  const [pending, startTransition] = useTransition();
  const {
    register,
    handleSubmit,
    setValue,
    setError,
    setFocus,
    getValues,
    formState: { errors, isSubmitted },
  } = useForm<QuickRegistrationInput, unknown, QuickRegistrationValues>({
    resolver: zodResolver(quickRegistrationSchema),
    mode: "onTouched",
    defaultValues: { fullName: "", mobile: "", dateOfBirth: "", email: "", password: "" },
  });

  const onSubmit = () => {
    if (pending) return;
    startTransition(async () => {
      setNotice(null);
      if (DASHBOARD_PREVIEW) {
        setNotice({ kind: "error", message: "Design preview: registration isn't available, and nothing was saved." });
        return;
      }
      // The raw input is sent; the Server Action validates it again. On success it redirects.
      const result = await registerMember(getValues());
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

        <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
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

        <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
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

          <div className="min-w-0">
            <label htmlFor={fieldId("password")} className="block text-sm font-medium text-ink">
              Password
            </label>
            <div className="mt-1.5">
              <PasswordInput
                id={fieldId("password")}
                autoComplete="new-password"
                maxLength={PASSWORD_MAX}
                className="h-12"
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={cn(
                  `${fieldId("password")}-hint`,
                  errors.password && `${fieldId("password")}-error`,
                )}
                {...register("password")}
              />
            </div>
            <ErrorText id={`${fieldId("password")}-error`} message={errors.password?.message} />
            <p id={`${fieldId("password")}-hint`} className="mt-1.5 text-sm text-ink-muted">
              At least {PASSWORD_MIN} characters.
            </p>
          </div>
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
          {pending ? "Creating your account…" : "Register free"}
        </button>

      </form>
    </div>
  );
}
