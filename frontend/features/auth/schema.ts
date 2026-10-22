import { parsePhoneNumberFromString } from "libphonenumber-js";
import { z } from "zod";

/**
 * SMS login is for Indian mobile numbers only. Mirrors the API's rule
 * (backend/apps/accounts/serializers.py): +91, then 10 digits starting 6–9.
 */
export const INDIA_MOBILE_E164 = /^\+91[6-9]\d{9}$/;

/** Room for the number typed with spaces and its own "+91 " prefix. */
export const PHONE_INPUT_MAX = 16;

/**
 * The number in E.164 form (+919876543210), or null if it isn't a valid Indian
 * mobile. Spaces, dashes and brackets are ignored, and a leading +91, 91 or 0
 * that people often type is dropped.
 */
export function toIndianMobile(input: string): string | null {
  let digits = input.replace(/[\s().-]/g, "");
  if (digits.startsWith("+91")) digits = digits.slice(3);
  else if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return /^[6-9]\d{9}$/.test(digits) ? `+91${digits}` : null;
}

/** Login step 1: the visitor's Indian mobile number, sent to the API in E.164 form. */
export const loginPhoneSchema = z
  .object({
    phone: z
      .string()
      .trim()
      .min(1, "Enter your mobile number.")
      .max(PHONE_INPUT_MAX, "This number is too long."),
  })
  .superRefine(({ phone }, ctx) => {
    if (!toIndianMobile(phone)) {
      ctx.addIssue({
        code: "custom",
        path: ["phone"],
        message: "Enter a valid 10-digit Indian mobile number, e.g. 98765 43210.",
      });
    }
  })
  .transform(({ phone }) => ({ phoneNumber: toIndianMobile(phone)! }));

export type LoginPhoneInput = z.input<typeof loginPhoneSchema>;
export type LoginPhoneValues = z.output<typeof loginPhoneSchema>;

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
