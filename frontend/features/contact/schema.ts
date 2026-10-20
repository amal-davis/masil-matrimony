import {
  getCountryCallingCode,
  isSupportedCountry,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js";
import { z } from "zod";

import { COUNTRY_NAMES } from "./countries";

/**
 * Contact form, mirroring the validation of POST /enquiries/
 * (backend/apps/enquiries/serializers.py). The backend re-validates everything.
 */

export const NAME_MAX = 100;
export const EMAIL_MAX = 254;
export const PHONE_INPUT_MAX = 30;
export const MESSAGE_MIN = 10;
export const MESSAGE_MAX = 2000;

export const DEFAULT_COUNTRY: CountryCode = "IN";

/** Every selectable country with its calling code, alphabetical by name. */
export const COUNTRY_OPTIONS = (Object.entries(COUNTRY_NAMES) as [CountryCode, string][]).map(([code, name]) => ({
  code,
  name,
  dialCode: `+${getCountryCallingCode(code)}`,
}));

/**
 * The number in E.164 form (e.g. +919876543210), or null if it isn't a valid
 * number for the chosen country. A number typed with its own +code wins over the
 * selected country.
 */
export function toE164(phone: string, country: CountryCode): string | null {
  const parsed = parsePhoneNumberFromString(phone, country);
  return parsed?.isValid() ? parsed.number : null;
}

const phoneError = (country: CountryCode) =>
  `Enter a valid phone number for ${COUNTRY_NAMES[country]} (+${getCountryCallingCode(country)}).`;

export const contactSchema = z
  .object({
    name: z
      .string()
      .transform((value) => value.trim().replace(/\s+/g, " "))
      .pipe(
        z
          .string()
          .min(2, "Enter your full name.")
          .max(NAME_MAX, `Keep the name under ${NAME_MAX} characters.`)
          .regex(/^\p{L}[\p{L}\p{M} .'-]*$/u, "Use letters, spaces, dots, apostrophes or hyphens only."),
      ),
    email: z
      .string()
      .trim()
      .min(1, "Enter your email address.")
      .max(EMAIL_MAX, "This email address is too long.")
      .pipe(z.email("Enter a valid email address, e.g. name@example.com.")),
    country: z.custom<CountryCode>(
      (value) => typeof value === "string" && isSupportedCountry(value),
      "Choose your country code.",
    ),
    phone: z
      .string()
      .trim()
      .min(1, "Enter your phone number.")
      .max(PHONE_INPUT_MAX, "This phone number is too long."),
    message: z
      .string()
      .trim()
      .min(1, "Enter your message.")
      .min(MESSAGE_MIN, `Please write at least ${MESSAGE_MIN} characters.`)
      .max(MESSAGE_MAX, `Keep the message under ${MESSAGE_MAX} characters.`),
    /** Spam trap, hidden from people. Sent as-is; the backend discards submissions that fill it. */
    website: z.string(),
  })
  .superRefine(
    ({ phone, country }, ctx) => {
      if (!toE164(phone, country)) ctx.addIssue({ code: "custom", path: ["phone"], message: phoneError(country) });
    },
    // Check the number as soon as phone and country are filled in, even while other fields have errors.
    { when: ({ issues }) => !issues.some((issue) => issue.path?.[0] === "phone" || issue.path?.[0] === "country") },
  )
  // The API takes one E.164 phone value; the country only helps read the number.
  .transform(({ country, phone, ...values }) => ({ ...values, phone: toE164(phone, country) ?? phone }));

export type ContactInput = z.input<typeof contactSchema>;
export type ContactValues = z.output<typeof contactSchema>;
export type ContactField = Exclude<keyof ContactValues, "website">;
