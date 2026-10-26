import type { CountryCode } from "libphonenumber-js";
import { z } from "zod";

import { emailField, invalidMobileMessage, mobileFields, toMobileE164 } from "@/features/auth/schema";

/**
 * Member registration (the hero quick-registration form). POST /auth/register/
 * sends a code by SMS to the mobile number; the account and draft profile
 * (created_for, gender, name, date of birth) are created once that code is
 * entered. No password: members sign in with an SMS code. Email is required:
 * payment receipts are sent there.
 * The API checks everything again.
 */

const createdForValues = ["self", "son", "daughter", "sibling", "relative"] as const;
const genderValues = ["female", "male"] as const;

type CreatedFor = (typeof createdForValues)[number];
type Gender = (typeof genderValues)[number];

export const createdForOptions: { value: CreatedFor; label: string }[] = [
  { value: "self", label: "Myself" },
  { value: "son", label: "My son" },
  { value: "daughter", label: "My daughter" },
  { value: "sibling", label: "My brother or sister" },
  { value: "relative", label: "A relative or friend" },
];

export const genderOptions: { value: Gender; label: string }[] = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
];

/** Minimum legal age of marriage in India (Prohibition of Child Marriage Act, 2006). */
export const MIN_AGE: Record<Gender, number> = { female: 18, male: 21 };
const MAX_AGE = 80;

/** Whole years between a YYYY-MM-DD date and today. */
export function ageOn(dateOfBirth: string, today = new Date()): number {
  const [year, month, day] = dateOfBirth.split("-").map(Number);
  const beforeBirthday =
    today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day);
  return today.getFullYear() - year - (beforeBirthday ? 1 : 0);
}

const fields = z.object({
  createdFor: z.enum(createdForValues, { error: "Choose who the profile is for." }),
  gender: z.enum(genderValues, { error: "Choose a gender." }),
  fullName: z
    .string()
    .trim()
    .min(2, "Enter the full name.")
    .max(60, "Keep the name under 60 characters.")
    .regex(/^[\p{L}\p{M}][\p{L}\p{M} .'-]*$/u, "Use letters, spaces, dots or hyphens only."),
  dateOfBirth: z.iso
    .date({ error: "Enter the date of birth." })
    .refine((value) => ageOn(value) <= MAX_AGE, "Check the date of birth."),
  country: mobileFields.country,
  mobile: mobileFields.phone,
  email: emailField,
  acceptTerms: z.literal(true, { error: "Please accept the terms and privacy policy." }),
});

const ageCheckInputs = fields.pick({ gender: true, dateOfBirth: true });

const mobileCheckInputs = fields.pick({ country: true, mobile: true });

export const quickRegistrationSchema = fields
  .refine(({ country, mobile }) => toMobileE164(mobile, country as CountryCode) !== null, {
    path: ["mobile"],
    error: (issue) => invalidMobileMessage((issue.input as { country: CountryCode }).country),
    // Run as soon as the country and number are filled in, even if other fields still have errors.
    when: (payload) => mobileCheckInputs.safeParse(payload.value).success,
  })
  .refine(
  (data) => ageOn(data.dateOfBirth) >= MIN_AGE[data.gender],
  {
    path: ["dateOfBirth"],
    error: (issue) => {
      const gender = (issue.input as { gender: Gender }).gender;
      return `The minimum age to register a ${gender === "female" ? "bride" : "groom"} is ${MIN_AGE[gender]}.`;
    },
    // Run as soon as gender and date are valid, even if other fields still have errors.
    when: (payload) => ageCheckInputs.safeParse(payload.value).success,
  },
);

export type QuickRegistrationInput = z.input<typeof quickRegistrationSchema>;
export type QuickRegistrationValues = z.output<typeof quickRegistrationSchema>;
