import { getCountryCallingCode, parsePhoneNumberFromString, type CountryCode } from "libphonenumber-js";
import { z } from "zod";

import { COUNTRY_NAMES } from "@/features/contact/countries";

/** Limits shared with the API (backend/apps/accounts). */
export const EMAIL_MAX = 254;

/** Room for a number typed with spaces, dashes and its own "+code". */
export const PHONE_INPUT_MAX = 20;

/** A required email address, trimmed (payment receipts are sent to it). Mirrors the API's check. */
export const emailField = z
  .string()
  .trim()
  .min(1, "Enter your email address. We send your payment receipts there.")
  .max(EMAIL_MAX, "This email address is too long.")
  .pipe(z.email("Enter a valid email address, e.g. name@example.com."));

function isCountryCode(value: string): value is CountryCode {
  if (!(value in COUNTRY_NAMES)) return false;
  try {
    getCountryCallingCode(value as CountryCode);
    return true;
  } catch {
    return false;
  }
}

/**
 * Countries whose mobile numbers can register and sign in: SMS codes are only
 * delivered where the provider is set up to send. Keep NEXT_PUBLIC_SMS_COUNTRIES
 * (ISO codes, e.g. "IN,AE") in step with the API's SMS_ALLOWED_COUNTRY_CODES
 * (calling codes, e.g. "91,971"); the API has the final say.
 */
export const SMS_COUNTRIES: CountryCode[] = (() => {
  const codes = (process.env.NEXT_PUBLIC_SMS_COUNTRIES ?? "IN")
    .split(",")
    .map((code) => code.trim().toUpperCase())
    .filter(isCountryCode);
  return codes.length ? [...new Set(codes)] : ["IN"];
})();

export const DEFAULT_SMS_COUNTRY: CountryCode = SMS_COUNTRIES[0];

const INDIA_MOBILE_E164 = /^\+91[6-9]\d{9}$/;

/**
 * The number in E.164 form (+919876543210), or null if it isn't a valid mobile
 * number in one of SMS_COUNTRIES. A number typed with its own "+code" wins over
 * the selected country; spaces, dashes and a leading 0 are ignored.
 */
export function toMobileE164(phone: string, country: CountryCode): string | null {
  const parsed = parsePhoneNumberFromString(phone.trim(), country);
  if (!parsed?.isValid()) return null;
  const allowed = SMS_COUNTRIES.some((code) => getCountryCallingCode(code) === parsed.countryCallingCode);
  if (!allowed) return null;
  // Same rule as the API: Indian numbers must be mobiles (10 digits starting 6-9).
  if (parsed.countryCallingCode === "91" && !INDIA_MOBILE_E164.test(parsed.number)) return null;
  return parsed.number;
}

export function invalidMobileMessage(country: CountryCode): string {
  return country === "IN"
    ? "Enter a valid 10-digit Indian mobile number, e.g. 98765 43210."
    : "Enter a valid mobile number for the selected country.";
}

/** The country picker and number field, checked together. */
export const mobileFields = {
  country: z.string().refine(
    (value) => SMS_COUNTRIES.includes(value as CountryCode),
    "Choose a country we can send SMS codes to.",
  ),
  phone: z.string().trim().min(1, "Enter your mobile number.").max(PHONE_INPUT_MAX, "This number is too long."),
};

/** Adds an error on `phone` when the number isn't a valid mobile in the chosen country. */
export function checkMobile(
  { country, phone }: { country: string; phone: string },
  ctx: z.RefinementCtx,
) {
  if (phone && !toMobileE164(phone, country as CountryCode)) {
    ctx.addIssue({ code: "custom", path: ["phone"], message: invalidMobileMessage(country as CountryCode) });
  }
}

/** Login step 1: the member's mobile number, sent to the API in E.164 form. */
export const loginPhoneSchema = z
  .object({ ...mobileFields, remember: z.boolean() })
  .superRefine(checkMobile)
  .transform(({ country, phone, remember }) => ({
    phoneNumber: toMobileE164(phone, country as CountryCode)!,
    remember,
  }));

export type LoginPhoneInput = z.input<typeof loginPhoneSchema>;
export type LoginPhoneValues = z.output<typeof loginPhoneSchema>;

/** "Change mobile number" during registration. */
export const changeMobileSchema = z
  .object(mobileFields)
  .superRefine(checkMobile)
  .transform(({ country, phone }) => ({ phoneNumber: toMobileE164(phone, country as CountryCode)! }));

export type ChangeMobileInput = z.input<typeof changeMobileSchema>;
export type ChangeMobileValues = z.output<typeof changeMobileSchema>;

/** A one-time code as typed: digits only (the API sets the exact length). */
export const OTP_PATTERN = /^\d{4,10}$/;

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
