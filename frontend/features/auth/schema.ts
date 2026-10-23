import { parsePhoneNumberFromString } from "libphonenumber-js";
import { z } from "zod";

/** Limits shared with the API (backend/apps/accounts/serializers.py). */
export const EMAIL_MAX = 254;
export const PASSWORD_MAX = 256;

/**
 * Mirrors the API's MinimumLengthValidator (AUTH_PASSWORD_VALIDATORS in
 * backend/config/settings/base.py). The API also rejects common passwords and
 * ones too like the member's details; those errors are shown when it answers.
 */
export const PASSWORD_MIN = 10;

/** An email address, trimmed. Shared with the registration form. */
export const emailField = z
  .string()
  .trim()
  .min(1, "Enter your email address.")
  .max(EMAIL_MAX, "This email address is too long.")
  .pipe(z.email("Enter a valid email address, e.g. name@example.com."));

/** Sign in. The password is never trimmed: spaces can be part of it. */
export const loginSchema = z.object({
  email: emailField,
  password: z.string().min(1, "Enter your password.").max(PASSWORD_MAX, "This password is too long."),
  remember: z.boolean(),
});

export type LoginValues = z.infer<typeof loginSchema>;

export const forgotPasswordSchema = z.object({ email: emailField });

/** A new password: the API's length and all-numeric rules. Shared with the registration form. */
export const newPasswordField = z
  .string()
  .min(PASSWORD_MIN, `Use at least ${PASSWORD_MIN} characters.`)
  .max(PASSWORD_MAX, "This password is too long.")
  .refine((value) => !/^\d+$/.test(value), "Use letters or symbols as well as numbers.");

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

/** Choosing a new password from an emailed link. */
export const resetPasswordSchema = z
  .object({
    password: newPasswordField,
    confirm: z.string().min(1, "Enter the password again."),
  })
  .refine((values) => values.password === values.confirm, {
    path: ["confirm"],
    message: "The passwords don't match.",
  });

export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

/** "+91 ••••• •3210": the country code and the last four digits only. */
export function maskPhoneNumber(e164: string): string {
  const parsed = parsePhoneNumberFromString(e164);
  if (!parsed) return `••••${e164.slice(-4)}`;
  const prefix = `+${parsed.countryCallingCode}`;
  const national = parsed.formatInternational().slice(prefix.length);
  let keep = 4;
  const masked = [...national]
    .reverse()
    .map((char) => (/\d/.test(char) ? (keep-- > 0 ? char : "•") : char))
    .reverse()
    .join("");
  return `${prefix}${masked}`;
}
