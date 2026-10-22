"use client";

import { useId, useState, useTransition } from "react";

import { controlClasses, ErrorText, Field, SegmentedOption, Select } from "@/components/ui/form-field";

import { createProfile } from "../actions";
import { createdForOptions, genderOptions, MIN_AGE } from "../profile-options";
import { Notice, primaryButton } from "./ui";

type Values = { created_for: string; display_name: string; gender: string; date_of_birth: string };

function ageOn(dateOfBirth: string) {
  const [year, month, day] = dateOfBirth.split("-").map(Number);
  const today = new Date();
  const before = today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day);
  return today.getFullYear() - year - (before ? 1 : 0);
}

function validate(values: Values): Partial<Record<keyof Values, string>> {
  const errors: Partial<Record<keyof Values, string>> = {};
  if (!values.created_for) errors.created_for = "Choose who the profile is for.";
  if (values.display_name.trim().length < 2) errors.display_name = "Enter the name to show on the profile.";
  else if (!/^[\p{L}\p{M}]+(?:[ .'-]+[\p{L}\p{M}]+)*\.?$/u.test(values.display_name.trim()))
    errors.display_name = "Use letters, spaces, dots, apostrophes or hyphens only.";
  if (!values.gender) errors.gender = "Choose a gender.";
  if (!values.date_of_birth) errors.date_of_birth = "Enter the date of birth.";
  else if (values.gender) {
    const minimum = MIN_AGE[values.gender as keyof typeof MIN_AGE];
    if (ageOn(values.date_of_birth) < minimum)
      errors.date_of_birth = `The minimum age for a ${values.gender === "female" ? "bride" : "groom"} is ${minimum}.`;
  }
  return errors;
}

/** First step for a member without a profile: who it's for and the details staff verify. */
export function CreateProfileForm({ defaultName }: { defaultName: string }) {
  const id = useId();
  const [values, setValues] = useState<Values>({ created_for: "", display_name: defaultName, gender: "", date_of_birth: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});
  const [failure, setFailure] = useState("");
  const [saving, startSaving] = useTransition();
  const set = (name: keyof Values, value: string) => setValues((current) => ({ ...current, [name]: value }));
  const fieldId = (name: string) => `${id}-${name}`;

  const submit = () => {
    const found = validate(values);
    setErrors(found);
    setFailure("");
    if (Object.keys(found).length) return;
    startSaving(async () => {
      const result = await createProfile({ ...values, display_name: values.display_name.trim() } as never);
      if (!result.ok) {
        setErrors(result.fieldErrors);
        setFailure(result.message);
      }
      // On success the page refreshes and shows the full profile editor.
    });
  };

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="rounded-xl border border-line bg-white p-5 sm:p-8"
    >
      <h2 className="text-xl font-semibold">Create your profile</h2>
      <p className="mt-1.5 text-[0.9375rem] text-ink-muted">
        Start with these details. Our team checks them when you submit your profile, so please enter them carefully.
      </p>

      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <Field id={fieldId("created_for")} label="This profile is for" required error={errors.created_for}>
          <Select
            id={fieldId("created_for")}
            value={values.created_for}
            onChange={(event) => set("created_for", event.target.value)}
            aria-invalid={errors.created_for ? true : undefined}
            aria-describedby={errors.created_for ? `${fieldId("created_for")}-error` : undefined}
          >
            <option value="">Choose…</option>
            {createdForOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </Field>

        <Field id={fieldId("display_name")} label="Name shown on the profile" required error={errors.display_name}
          hint="A first name is enough. Other members see this name.">
          <input
            id={fieldId("display_name")}
            type="text"
            autoComplete="given-name"
            maxLength={60}
            value={values.display_name}
            onChange={(event) => set("display_name", event.target.value)}
            className={controlClasses}
            aria-invalid={errors.display_name ? true : undefined}
            aria-describedby={`${fieldId("display_name")}-hint ${errors.display_name ? `${fieldId("display_name")}-error` : ""}`}
          />
        </Field>

        <fieldset className="min-w-0">
          <legend className="text-sm font-medium text-ink">
            Gender<span aria-hidden="true" className="ml-0.5 text-danger">*</span>
          </legend>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {genderOptions.map((option) => (
              <SegmentedOption
                key={option.value}
                name={fieldId("gender")}
                value={option.value}
                label={option.label}
                checked={values.gender === option.value}
                invalid={Boolean(errors.gender)}
                onChange={() => set("gender", option.value)}
              />
            ))}
          </div>
          <ErrorText id={`${fieldId("gender")}-error`} message={errors.gender} />
        </fieldset>

        <Field id={fieldId("date_of_birth")} label="Date of birth" required error={errors.date_of_birth}
          hint="Other members see the age, never this date.">
          <input
            id={fieldId("date_of_birth")}
            type="date"
            value={values.date_of_birth}
            onChange={(event) => set("date_of_birth", event.target.value)}
            className={controlClasses}
            aria-invalid={errors.date_of_birth ? true : undefined}
            aria-describedby={`${fieldId("date_of_birth")}-hint ${errors.date_of_birth ? `${fieldId("date_of_birth")}-error` : ""}`}
          />
        </Field>
      </div>

      <div role="alert" className="mt-5 empty:hidden">
        {failure && <Notice tone="danger">{failure}</Notice>}
      </div>

      <button type="submit" disabled={saving} className={`${primaryButton} mt-6 w-full sm:w-auto`}>
        {saving ? "Creating…" : "Create my profile"}
      </button>
    </form>
  );
}
