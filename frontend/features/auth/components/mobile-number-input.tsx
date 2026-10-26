"use client";

import type { CountryCode } from "libphonenumber-js";
import type { ComponentProps } from "react";

import { controlClasses, ErrorText } from "@/components/ui/form-field";
import { CountryCodePicker } from "@/features/contact/components/country-code-picker";
import { COUNTRY_OPTIONS } from "@/features/contact/schema";
import { cn } from "@/lib/utils";

import { PHONE_INPUT_MAX, SMS_COUNTRIES } from "../schema";

/** Only the countries SMS codes can be delivered to (NEXT_PUBLIC_SMS_COUNTRIES). */
const SMS_COUNTRY_OPTIONS = COUNTRY_OPTIONS.filter((option) => SMS_COUNTRIES.includes(option.code));

/**
 * Mobile number with its country calling code: a country picker beside the
 * number field. `inputProps` are spread on the number <input> (e.g. react-hook-form's register()).
 */
export function MobileNumberInput({
  id,
  label = "Mobile number",
  country,
  onCountryChange,
  error,
  hint,
  tall = false,
  disabled,
  inputProps,
}: {
  id: string;
  label?: string;
  country: CountryCode;
  onCountryChange: (code: CountryCode) => void;
  error?: string;
  hint?: string;
  /** The sign-in pages' 52px fields instead of the forms' 48px ones. */
  tall?: boolean;
  disabled?: boolean;
  inputProps: Omit<ComponentProps<"input">, "id" | "type">;
}) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <div className="mt-1.5 flex min-w-0 gap-2">
        <CountryCodePicker
          value={country}
          onChange={onCountryChange}
          options={SMS_COUNTRY_OPTIONS}
          disabled={disabled}
          className={cn(tall && "h-13")}
        />
        <input
          id={id}
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          maxLength={PHONE_INPUT_MAX}
          placeholder={country === "IN" ? "98765 43210" : undefined}
          disabled={disabled}
          className={cn(controlClasses, "min-w-0", tall && "h-13 sm:text-lg sm:tracking-wide")}
          aria-invalid={error ? true : undefined}
          aria-describedby={cn(hint && hintId, error && errorId) || undefined}
          {...inputProps}
        />
      </div>
      <ErrorText id={errorId} message={error} />
      {hint && (
        <p id={hintId} className="mt-1.5 text-sm text-ink-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
