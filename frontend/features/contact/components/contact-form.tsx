"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { controlClasses, errorProps, Field, textareaClasses } from "@/components/ui/form-field";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { submitEnquiry } from "../api";
import {
  contactSchema,
  DEFAULT_COUNTRY,
  EMAIL_MAX,
  MESSAGE_MAX,
  NAME_MAX,
  PHONE_INPUT_MAX,
  type ContactField,
  type ContactInput,
  type ContactValues,
} from "../schema";
import { CountryCodePicker } from "./country-code-picker";

type Status =
  | { kind: "idle" }
  | { kind: "success" }
  | { kind: "error"; message: string };

const FIELDS: ContactField[] = ["name", "email", "phone", "message"];

const GENERIC_ERROR ="We couldn't submit your message right now. Please try again.";

/** A friendly message for a failed submission. Field errors are shown on the fields themselves. */
function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return GENERIC_ERROR;
  if (error.isNetworkError) {
    return "We couldn't reach our server. Please check your connection and try again.";
  }
  if (error.status === 429) {
    return "You've sent several messages recently. Please wait a while before trying again.";
  }
  if (error.status === 400) return "Please correct the highlighted fields and try again.";
  return GENERIC_ERROR;
}

/**
 * Contact form. Sends the message to POST /enquiries/, which stores it for staff.
 * Success is shown only once the API has accepted the message; on failure the
 * visitor's text stays in the form so nothing has to be retyped.
 */
export function ContactForm() {
  const id = useId();
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const {
    register,
    handleSubmit,
    reset,
    setError,
    trigger,
    getFieldState,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ContactInput, unknown, ContactValues>({
    resolver: zodResolver(contactSchema),
    mode: "onTouched",
    defaultValues: { name: "", email: "", country: DEFAULT_COUNTRY, phone: "", message: "", website: "" },
  });

  const onSubmit = async (values: ContactValues) => {
    setStatus({ kind: "idle" });
    try {
      await submitEnquiry(values);
    } catch (error) {
      if (error instanceof ApiError && error.status === 400 && error.body) {
        for (const field of FIELDS) {
          const messages = error.body[field];
          if (Array.isArray(messages) && typeof messages[0] === "string") {
            setError(field, { type: "server", message: messages[0] });
          }
        }
      }
      setStatus({ kind: "error", message: errorMessage(error) });
      return;
    }
    reset();
    setStatus({ kind: "success" });
  };

  const fieldId = (name: string) => `${id}-${name}`;
  const messageLength = useWatch({ control, name: "message" }).trim().length;

  return (
    <div className="rounded-xl border border-line bg-white p-5 sm:p-8">
      <h2 id={fieldId("title")} className="text-2xl font-semibold sm:text-3xl">
        Send Us a Message
      </h2>
      <p className="mt-2 text-[0.9375rem] text-ink-muted">
        All fields are required<span aria-hidden="true"> (marked *)</span>.
      </p>

      <form
        noValidate
        aria-labelledby={fieldId("title")}
        onSubmit={handleSubmit(onSubmit)}
        className="mt-6 flex flex-col gap-5"
      >
        <div className="grid gap-5 md:grid-cols-2">
          <Field id={fieldId("name")} label="Full Name" required error={errors.name?.message}>
            <input
              id={fieldId("name")}
              type="text"
              autoComplete="name"
              placeholder="Enter your full name"
              maxLength={NAME_MAX}
              required
              className={controlClasses}
              {...errorProps(fieldId("name"), errors.name?.message)}
              {...register("name")}
            />
          </Field>

          <Field id={fieldId("phone")} label="Phone Number" required error={errors.phone?.message}>
            <div className="flex gap-2">
              <Controller
                control={control}
                name="country"
                render={({ field }) => (
                  <CountryCodePicker
                    value={field.value}
                    onBlur={field.onBlur}
                    onChange={(code) => {
                      field.onChange(code);
                      // Re-check a number already entered against the newly chosen country.
                      if (getFieldState("phone").isTouched) void trigger("phone");
                    }}
                  />
                )}
              />
              <input
                id={fieldId("phone")}
                type="tel"
                inputMode="tel"
                autoComplete="tel-national"
                placeholder="Enter your phone number"
                maxLength={PHONE_INPUT_MAX}
                required
                className={controlClasses}
                aria-invalid={errors.phone ? true : undefined}
                aria-describedby={cn(`${fieldId("phone")}-hint`, errors.phone && `${fieldId("phone")}-error`)}
                {...register("phone")}
              />
            </div>
            <p id={`${fieldId("phone")}-hint`} className="mt-1.5 text-sm text-ink-muted">
              Choose your country code, then enter your number.
            </p>
          </Field>
        </div>

        <Field id={fieldId("email")} label="Email Address" required error={errors.email?.message}>
          <input
            id={fieldId("email")}
            type="email"
            autoComplete="email"
            placeholder="Enter your email address"
            maxLength={EMAIL_MAX}
            required
            className={controlClasses}
            {...errorProps(fieldId("email"), errors.email?.message)}
            {...register("email")}
          />
        </Field>

        <Field id={fieldId("message")} label="Message" required error={errors.message?.message}>
          <textarea
            id={fieldId("message")}
            rows={6}
            placeholder="How can we help you?"
            maxLength={MESSAGE_MAX}
            required
            className={textareaClasses}
            aria-invalid={errors.message ? true : undefined}
            aria-describedby={cn(`${fieldId("message")}-count`, errors.message && `${fieldId("message")}-error`)}
            {...register("message")}
          />
          <p id={`${fieldId("message")}-count`} className="mt-1.5 text-right text-sm text-ink-muted tabular-nums">
            {messageLength} / {MESSAGE_MAX}
            <span className="sr-only"> characters</span>
          </p>
        </Field>

        {/* Spam trap: invisible to people and skipped by keyboard and screen readers. */}
        <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
          <label htmlFor={fieldId("website")}>Leave this field empty</label>
          <input id={fieldId("website")} type="text" tabIndex={-1} autoComplete="off" {...register("website")} />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-13 items-center justify-center rounded-md bg-wine-600 px-8 text-base font-medium text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-wait disabled:opacity-60 sm:self-start"
        >
          {isSubmitting ? "Sending…" : "Send Message"}
        </button>

        <div role="status" aria-live="polite">
          {status.kind === "success" && (
            <p className="flex items-start gap-2.5 rounded-md border border-success/40 bg-success/5 px-4 py-3 text-[0.9375rem] text-ink">
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-success">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.86-9.81a.75.75 0 0 0-1.22-.88l-3.24 4.5-1.6-1.6a.75.75 0 1 0-1.06 1.06l2.22 2.22a.75.75 0 0 0 1.14-.09l3.76-5.21Z"
                  clipRule="evenodd"
                />
              </svg>
              Thank you for contacting Massil Matrimony. Your message has been submitted successfully.
            </p>
          )}
        </div>
        <div role="alert">
          {status.kind === "error" && (
            <p className="rounded-md border border-danger/40 bg-danger/5 px-4 py-3 text-[0.9375rem] text-ink">
              {status.message}
            </p>
          )}
        </div>
      </form>
    </div>
  );
}
