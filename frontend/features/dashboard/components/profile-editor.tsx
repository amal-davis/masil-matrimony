"use client";

import { useEffect, useId, useState, useTransition, type ReactNode } from "react";

import { controlClasses, ErrorText, Select, textareaClasses } from "@/components/ui/form-field";
import { cn } from "@/lib/utils";

import { updatePartnerPreference, updateProfile } from "../actions";
import {
  ageOptions,
  annualIncomeOptions,
  communitiesFor,
  createdForOptions,
  dietOptions,
  employmentTypeOptions,
  familyTypeOptions,
  familyValuesOptions,
  genderOptions,
  heightOptions,
  maritalStatusOptions,
  motherTongueOptions,
  optionLabel,
  religionOptions,
  type Option,
} from "../profile-options";
import type { OwnProfile } from "../types";
import { ConfirmDialog } from "./confirm-dialog";
import { PencilIcon } from "./icons";
import { Notice, primaryButton, quietButton, secondaryButton } from "./ui";

type Kind = "text" | "textarea" | "select" | "date" | "tags" | "checkbox" | "multi";

interface FieldDef {
  name: string;
  label: string;
  kind: Kind;
  options?: readonly Option[] | ((values: FormValues) => readonly Option[]);
  hint?: string;
  maxLength?: number;
  required?: boolean;
  /** Numeric value (sent as a number or null). */
  numeric?: boolean;
  /** Fixed once the profile is submitted (the API enforces this too). */
  identity?: boolean;
  wide?: boolean;
}

type FormValue = string | boolean | string[];
type FormValues = Record<string, FormValue>;

export interface SectionDef {
  id: string;
  title: string;
  description?: string;
  fields: FieldDef[];
  /** Which API resource the section saves to. */
  target: "profile" | "preference";
}

const heightLabel = (cm: string) => optionLabel(heightOptions, cm) || (cm ? `${cm} cm` : "");

export const profileSections: SectionDef[] = [
  {
    id: "personal",
    title: "Personal Information",
    target: "profile",
    fields: [
      { name: "display_name", label: "Name shown on your profile", kind: "text", maxLength: 60, required: true, identity: true },
      { name: "created_for", label: "Profile created for", kind: "select", options: createdForOptions, required: true },
      { name: "gender", label: "Gender", kind: "select", options: genderOptions, required: true, identity: true },
      { name: "date_of_birth", label: "Date of birth", kind: "date", required: true, identity: true, hint: "Other members see your age, never this date." },
      { name: "height_cm", label: "Height", kind: "select", options: heightOptions, numeric: true },
      { name: "marital_status", label: "Marital status", kind: "select", options: maritalStatusOptions },
      { name: "religion", label: "Religion", kind: "select", options: religionOptions },
      { name: "community", label: "Community / denomination", kind: "select", options: (values) => communitiesFor(String(values.religion ?? "")) },
      { name: "mother_tongue", label: "Mother tongue", kind: "select", options: motherTongueOptions },
      { name: "city", label: "Current city", kind: "text", maxLength: 60 },
      { name: "district", label: "District", kind: "text", maxLength: 60 },
      { name: "state", label: "State", kind: "text", maxLength: 60 },
      { name: "country", label: "Country", kind: "text", maxLength: 60 },
      { name: "native_place", label: "Native place", kind: "text", maxLength: 80 },
    ],
  },
  {
    id: "about",
    title: "About Me",
    description: "A few sentences about yourself, your values and what you're looking for.",
    target: "profile",
    fields: [{ name: "about", label: "About me", kind: "textarea", maxLength: 2000, wide: true }],
  },
  {
    id: "career",
    title: "Education & Career",
    target: "profile",
    fields: [
      { name: "highest_education", label: "Highest education", kind: "text", maxLength: 80, hint: "For example B.Tech, MBA, M.Sc." },
      { name: "education_detail", label: "Qualification details", kind: "text", maxLength: 120 },
      { name: "institution", label: "College or institution", kind: "text", maxLength: 120 },
      { name: "occupation", label: "Occupation", kind: "text", maxLength: 80 },
      { name: "employment_type", label: "Employment type", kind: "select", options: employmentTypeOptions },
      { name: "work_location", label: "Work location", kind: "text", maxLength: 80 },
      { name: "annual_income", label: "Annual income", kind: "select", options: annualIncomeOptions },
      { name: "income_visible", label: "Show my income to other members", kind: "checkbox", hint: "Off by default: only you can see your income." },
    ],
  },
  {
    id: "family",
    title: "Family Background",
    target: "profile",
    fields: [
      { name: "family_type", label: "Family type", kind: "select", options: familyTypeOptions },
      { name: "family_values", label: "Family values", kind: "select", options: familyValuesOptions },
      { name: "family_location", label: "Family location", kind: "text", maxLength: 80 },
      { name: "father_occupation", label: "Father's occupation", kind: "text", maxLength: 80 },
      { name: "mother_occupation", label: "Mother's occupation", kind: "text", maxLength: 80 },
      { name: "siblings", label: "Siblings", kind: "text", maxLength: 160, hint: "For example: one elder sister, married" },
    ],
  },
  {
    id: "lifestyle",
    title: "Lifestyle & Interests",
    target: "profile",
    fields: [
      { name: "diet", label: "Diet", kind: "select", options: dietOptions },
      { name: "languages", label: "Languages known", kind: "tags", hint: "Separate with commas, up to 10." },
      { name: "hobbies", label: "Hobbies", kind: "tags", hint: "Separate with commas, up to 10." },
      { name: "interests", label: "Interests", kind: "tags", hint: "Separate with commas, up to 10." },
    ],
  },
  {
    id: "preferences",
    title: "Partner Preferences",
    description: "Used to suggest matches. Leave a field empty if you have no preference.",
    target: "preference",
    fields: [
      { name: "age_min", label: "Minimum age", kind: "select", options: ageOptions, numeric: true },
      { name: "age_max", label: "Maximum age", kind: "select", options: ageOptions, numeric: true },
      { name: "height_min_cm", label: "Minimum height", kind: "select", options: heightOptions, numeric: true },
      { name: "height_max_cm", label: "Maximum height", kind: "select", options: heightOptions, numeric: true },
      { name: "marital_statuses", label: "Marital status", kind: "multi", options: maritalStatusOptions, wide: true },
      { name: "religions", label: "Religion", kind: "multi", options: religionOptions, wide: true },
      { name: "locations", label: "Preferred locations", kind: "text", maxLength: 120 },
      { name: "education", label: "Education", kind: "text", maxLength: 120 },
      { name: "occupation", label: "Occupation", kind: "text", maxLength: 120 },
      { name: "notes", label: "Anything else", kind: "textarea", maxLength: 500, wide: true },
    ],
  },
];

// --- Value conversion ------------------------------------------------------

function sourceFor(section: SectionDef, profile: OwnProfile): Record<string, unknown> {
  return section.target === "preference" ? (profile.partner_preference as unknown as Record<string, unknown>) : (profile as unknown as Record<string, unknown>);
}

function toFormValues(section: SectionDef, profile: OwnProfile): FormValues {
  const source = sourceFor(section, profile);
  return Object.fromEntries(
    section.fields.map((field) => {
      const value = source[field.name];
      if (field.kind === "checkbox") return [field.name, Boolean(value)];
      if (field.kind === "multi") return [field.name, Array.isArray(value) ? value.map(String) : []];
      if (field.kind === "tags") return [field.name, Array.isArray(value) ? value.join(", ") : ""];
      return [field.name, value === null || value === undefined ? "" : String(value)];
    }),
  );
}

function toPayloadValue(field: FieldDef, value: FormValue): unknown {
  if (field.kind === "checkbox") return Boolean(value);
  if (field.kind === "multi") return value;
  if (field.kind === "tags") return String(value).split(",").map((item) => item.trim()).filter(Boolean);
  if (field.numeric) return value === "" ? null : Number(value);
  return typeof value === "string" ? value.trim() : value;
}

function displayValue(field: FieldDef, value: FormValue, values: FormValues): ReactNode {
  if (field.kind === "checkbox") return value ? "Yes" : "No";
  if (field.kind === "multi") {
    const labels = (value as string[]).map((item) => optionLabel(field.options as Option[], item)).filter(Boolean);
    return labels.length ? labels.join(", ") : "";
  }
  if (field.name === "height_cm" || field.name.startsWith("height_")) return heightLabel(String(value));
  if (field.kind === "select") {
    const options = typeof field.options === "function" ? field.options(values) : field.options ?? [];
    return optionLabel(options, String(value)) || String(value);
  }
  if (field.kind === "date" && value) {
    return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
  }
  return String(value);
}

/** Checks done before saving; the API repeats them and has the final say. */
function validate(section: SectionDef, values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of section.fields) {
    const value = values[field.name];
    if (field.required && (value === "" || value === undefined)) errors[field.name] = `Enter your ${field.label.toLowerCase()}.`;
    if (field.maxLength && typeof value === "string" && value.trim().length > field.maxLength) {
      errors[field.name] = `Keep this under ${field.maxLength} characters.`;
    }
    if (field.kind === "tags" && String(value).split(",").filter((item) => item.trim()).length > 10) {
      errors[field.name] = "Add up to 10 entries.";
    }
  }
  for (const [low, high, name] of [["age_min", "age_max", "age"], ["height_min_cm", "height_max_cm", "height"]] as const) {
    if (values[low] && values[high] && Number(values[low]) > Number(values[high])) {
      errors[high] = `The maximum ${name} must not be less than the minimum.`;
    }
  }
  return errors;
}

// --- Section ---------------------------------------------------------------

function FieldControl({
  id,
  field,
  value,
  values,
  error,
  disabled,
  onChange,
}: {
  id: string;
  field: FieldDef;
  value: FormValue;
  values: FormValues;
  error?: string;
  disabled: boolean;
  onChange: (value: FormValue) => void;
}) {
  const describedBy = cn(field.hint && `${id}-hint`, error && `${id}-error`) || undefined;
  const common = { id, disabled, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy };
  const options = typeof field.options === "function" ? field.options(values) : field.options ?? [];

  let control: ReactNode;
  switch (field.kind) {
    case "textarea":
      control = (
        <textarea {...common} rows={field.maxLength && field.maxLength > 600 ? 7 : 4} maxLength={field.maxLength}
          value={String(value)} onChange={(event) => onChange(event.target.value)} className={textareaClasses} />
      );
      break;
    case "select":
      control = (
        <Select {...common} value={String(value)} onChange={(event) => onChange(event.target.value)} disabled={disabled || options.length === 0}>
          <option value="">{options.length === 0 ? "Not applicable" : "Not specified"}</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </Select>
      );
      break;
    case "date":
      control = <input {...common} type="date" value={String(value)} onChange={(event) => onChange(event.target.value)} className={controlClasses} />;
      break;
    case "checkbox":
      return (
        <div className="sm:col-span-2">
          <label className="flex min-h-11 items-start gap-3">
            <input {...common} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)}
              className="mt-0.5 size-5 shrink-0 accent-wine-600" />
            <span className="text-[0.9375rem] font-medium text-ink">{field.label}</span>
          </label>
          {field.hint && <p id={`${id}-hint`} className="mt-1 ml-8 text-sm text-ink-muted">{field.hint}</p>}
          <ErrorText id={`${id}-error`} message={error} />
        </div>
      );
    case "multi":
      return (
        <fieldset className={cn("min-w-0", field.wide && "sm:col-span-2")} aria-describedby={describedBy}>
          <legend className="text-sm font-medium text-ink">{field.label}</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.map((option) => {
              const selected = (value as string[]).includes(option.value);
              return (
                <label key={option.value} className={cn(
                  "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 text-[0.9375rem] transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-wine-600",
                  selected ? "border-wine-600 bg-brand-50 text-wine-600" : "border-field-line text-ink",
                )}>
                  <input type="checkbox" className="sr-only" checked={selected} disabled={disabled}
                    onChange={(event) => onChange(event.target.checked ? [...(value as string[]), option.value] : (value as string[]).filter((item) => item !== option.value))} />
                  {option.label}
                </label>
              );
            })}
          </div>
          <ErrorText id={`${id}-error`} message={error} />
        </fieldset>
      );
    default:
      control = (
        <input {...common} type="text" maxLength={field.maxLength} value={String(value)} onChange={(event) => onChange(event.target.value)}
          className={controlClasses} />
      );
  }

  return (
    <div className={cn("min-w-0", field.wide && "sm:col-span-2")}>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {field.label}
        {field.required && <span aria-hidden="true" className="ml-0.5 text-danger">*</span>}
      </label>
      <div className="mt-1.5">{control}</div>
      {field.hint && <p id={`${id}-hint`} className="mt-1.5 text-sm text-ink-muted">{field.hint}</p>}
      <ErrorText id={`${id}-error`} message={error} />
    </div>
  );
}

function ProfileSection({
  section,
  profile,
  editing,
  onEdit,
  onDone,
  onDirtyChange,
}: {
  section: SectionDef;
  profile: OwnProfile;
  editing: boolean;
  onEdit: () => void;
  onDone: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const id = useId();
  const saved = toFormValues(section, profile);
  const [values, setValues] = useState<FormValues>(saved);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [saving, startSaving] = useTransition();

  const changed = section.fields.filter((field) => JSON.stringify(values[field.name]) !== JSON.stringify(saved[field.name]));
  const dirty = editing && changed.length > 0;

  // Block body: an effect's return value is treated as its cleanup function.
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  const startEditing = () => {
    setValues(saved);
    setErrors({});
    setMessage(null);
    onEdit();
  };

  const discard = () => {
    setConfirmDiscard(false);
    setValues(saved);
    setErrors({});
    onDone();
  };

  const save = () => {
    const found = validate(section, values);
    setErrors(found);
    if (Object.keys(found).length) {
      setMessage({ tone: "danger", text: "Please correct the highlighted fields." });
      return;
    }
    if (changed.length === 0) {
      onDone();
      return;
    }
    // Only the fields that changed are sent, so other saved details are never overwritten.
    const payload = Object.fromEntries(changed.map((field) => [field.name, toPayloadValue(field, values[field.name])]));
    if (section.id === "personal" && "religion" in payload && !("community" in payload)) {
      const community = String(values.community ?? "");
      if (community && !communitiesFor(String(values.religion)).some((option) => option.value === community)) payload.community = "";
    }
    startSaving(async () => {
      const result = section.target === "preference" ? await updatePartnerPreference(payload) : await updateProfile(payload);
      if (result.ok) {
        setMessage({ tone: "success", text: `${section.title} saved.` });
        onDone();
      } else {
        setErrors(result.fieldErrors);
        setMessage({ tone: "danger", text: result.message });
      }
    });
  };

  const titleId = `${id}-title`;
  const shown = section.fields.filter((field) => field.kind !== "checkbox" || section.id !== "career" || values.annual_income);

  return (
    // `id` is the target of the page's section tabs; scroll-margin clears the sticky bars.
    <section
      id={section.id}
      aria-labelledby={titleId}
      className={cn(
        "scroll-mt-36 rounded-xl border bg-white transition-colors",
        editing ? "border-wine-600/40 ring-4 ring-brand-50" : "border-line",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4 sm:px-6">
        <div className="min-w-0">
          <h2 id={titleId} className="text-base font-semibold sm:text-[1.0625rem]">{section.title}</h2>
          {section.description && <p className="mt-0.5 text-sm text-ink-muted">{section.description}</p>}
        </div>
        {editing ? (
          <span className="text-sm font-medium text-wine-600">Editing</span>
        ) : (
          <button type="button" onClick={startEditing} className={quietButton} aria-label={`Edit ${section.title}`}>
            <PencilIcon className="size-4.5" />
            Edit
          </button>
        )}
      </div>

      <div className="p-5 sm:p-6">
        {editing ? (
          <form noValidate onSubmit={(event) => { event.preventDefault(); save(); }}>
            <div className="grid gap-5 sm:grid-cols-2">
              {shown.map((field) => (
                <FieldControl
                  key={field.name}
                  id={`${id}-${field.name}`}
                  field={field}
                  value={values[field.name]}
                  values={values}
                  error={errors[field.name]}
                  disabled={saving || (field.identity === true && profile.identity_locked)}
                  onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
                />
              ))}
            </div>
            {section.fields.some((field) => field.identity) && profile.identity_locked && (
              <p className="mt-4 text-sm text-ink-muted">
                Name, gender and date of birth were checked when you submitted your profile. To correct them, please contact us.
              </p>
            )}
            <div role="alert" className="mt-5 empty:hidden">
              {message?.tone === "danger" && <Notice tone="danger">{message.text}</Notice>}
            </div>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" onClick={() => (dirty ? setConfirmDiscard(true) : discard())} disabled={saving} className={secondaryButton}>
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButton}>
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        ) : (
          <>
            <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
              {section.fields.map((field) => {
                const shownValue = displayValue(field, saved[field.name], saved);
                return (
                  <div key={field.name} className={cn("min-w-0", field.wide && "sm:col-span-2")}>
                    <dt className="text-sm text-ink-muted">{field.label}</dt>
                    <dd className={cn("mt-0.5 break-words whitespace-pre-line", shownValue ? "font-medium text-ink" : "text-ink-muted italic")}>
                      {shownValue || "Not added"}
                    </dd>
                  </div>
                );
              })}
            </dl>
            <div role="status" className="empty:hidden">
              {message?.tone === "success" && <Notice tone="success" className="mt-5">{message.text}</Notice>}
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={confirmDiscard}
        title="Discard your changes?"
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        tone="danger"
        onConfirm={discard}
        onCancel={() => setConfirmDiscard(false)}
      >
        The changes you made to {section.title} haven&apos;t been saved.
      </ConfirmDialog>
    </section>
  );
}

/** All biodata sections. One section is edited at a time; leaving the page with unsaved edits asks first. */
export function ProfileEditor({ profile }: { profile: OwnProfile }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const requestEdit = (id: string) => (dirty && editing !== id ? setPending(id) : setEditing(id));

  return (
    <div className="flex flex-col gap-6">
      {profileSections.map((section) => (
        <ProfileSection
          key={section.id}
          section={section}
          profile={profile}
          editing={editing === section.id}
          onEdit={() => requestEdit(section.id)}
          onDone={() => {
            // A closed section has nothing unsaved (it was saved or discarded).
            setEditing(null);
            setDirty(false);
          }}
          onDirtyChange={(value) => {
            if (editing === section.id) setDirty(value);
          }}
        />
      ))}
      <ConfirmDialog
        open={pending !== null}
        title="Discard unsaved changes?"
        confirmLabel="Discard and continue"
        cancelLabel="Keep editing"
        tone="danger"
        onConfirm={() => {
          setDirty(false);
          setEditing(pending);
          setPending(null);
        }}
        onCancel={() => setPending(null)}
      >
        You have unsaved changes in another section. They&apos;ll be lost if you continue.
      </ConfirmDialog>
    </div>
  );
}
