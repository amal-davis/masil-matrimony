import { z } from "zod";

import { emailField, newPasswordField } from "@/features/auth/schema";

/**
 * Member registration (the hero quick-registration form). Creates the account
 * (email, password, mobile) and a draft profile (created_for, gender, name,
 * date of birth) through POST /auth/register/. The API checks everything again.
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
  mobile: z
    .string()
    .transform((value) => value.replace(/[\s-]/g, ""))
    .pipe(z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number.")),
  email: emailField,
  // One password field: the form offers show/hide instead of a confirmation box.
  password: newPasswordField,
  acceptTerms: z.literal(true, { error: "Please accept the terms and privacy policy." }),
});

const ageCheckInputs = fields.pick({ gender: true, dateOfBirth: true });

export const quickRegistrationSchema = fields.refine(
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
