import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { formatHeight, formatLocation, formatRange } from "../format";
import type { ProfileDetail } from "../types";

export type DetailItem = { label: string; value: string | undefined };

/** A titled white card for one part of the biodata. */
export function ProfileSection({
  id,
  title,
  className,
  children,
}: {
  id: string;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={cn("min-w-0 rounded-xl border border-line bg-white p-5 sm:p-7", className)}>
      <h2 id={id} className="text-xl font-semibold sm:text-[1.375rem]">
        {title}
      </h2>
      <div className="mt-4 border-t border-line pt-5">{children}</div>
    </section>
  );
}

/** Label/value pairs; items without a value are left out rather than shown as blanks. */
export function DetailList({ items, className }: { items: DetailItem[]; className?: string }) {
  const present = items.filter((item): item is { label: string; value: string } => Boolean(item.value));
  return (
    <dl className={cn("grid gap-x-8 gap-y-4 min-[400px]:grid-cols-2", className)}>
      {present.map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="text-sm text-ink-muted">{label}</dt>
          <dd className="mt-0.5 text-base font-medium break-words text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export const hasDetails = (items: DetailItem[]) => items.some((item) => Boolean(item.value));

function Tags({ label, values }: { label: string; values?: string[] }) {
  if (!values?.length) return null;
  return (
    <div>
      <h3 className="font-sans text-sm font-normal text-ink-muted">{label}</h3>
      <ul className="mt-2 flex flex-wrap gap-2">
        {values.map((value) => (
          <li key={value} className="rounded-full border border-line bg-mist px-3 py-1 text-sm font-medium text-ink">
            {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function personalDetails(profile: ProfileDetail): DetailItem[] {
  return [
    { label: "Age", value: `${profile.age} years` },
    { label: "Height", value: profile.heightCm ? formatHeight(profile.heightCm) : undefined },
    { label: "Marital Status", value: profile.maritalStatus },
    { label: "Religion", value: profile.religion },
    { label: "Community", value: profile.community },
    { label: "Mother Tongue", value: profile.motherTongue },
    { label: "Native Place", value: profile.nativePlace },
    { label: "Current Location", value: formatLocation(profile.location) },
    { label: "Country", value: profile.location.country },
  ];
}

export function careerDetails(profile: ProfileDetail): DetailItem[] {
  const career = profile.career ?? {};
  return [
    { label: "Highest Qualification", value: career.qualification ?? profile.education },
    { label: "College / University", value: career.institution },
    { label: "Profession", value: career.profession ?? profile.profession },
    { label: "Employment Type", value: career.employmentType },
    { label: "Work Location", value: career.workLocation },
    { label: "Annual Income", value: career.annualIncome },
  ];
}

export function familyDetails(profile: ProfileDetail): DetailItem[] {
  const family = profile.family ?? {};
  return [
    { label: "Family Type", value: family.type },
    { label: "Family Values", value: family.values },
    { label: "Family Location", value: family.location },
    { label: "Father's Occupation", value: family.fatherOccupation },
    { label: "Mother's Occupation", value: family.motherOccupation },
    { label: "Siblings", value: family.siblings },
  ];
}

export function partnerDetails(profile: ProfileDetail): DetailItem[] {
  const prefs = profile.partnerPreferences ?? {};
  return [
    { label: "Age", value: prefs.ageRange ? `${formatRange(prefs.ageRange)} years` : undefined },
    { label: "Height", value: prefs.heightRangeCm ? formatRange(prefs.heightRangeCm, formatHeight) : undefined },
    { label: "Marital Status", value: prefs.maritalStatus },
    { label: "Religion", value: prefs.religion },
    { label: "Education", value: prefs.education },
    { label: "Location", value: prefs.location },
  ];
}

export function hasLifestyle(profile: ProfileDetail) {
  const lifestyle = profile.lifestyle;
  return Boolean(
    lifestyle && (lifestyle.diet || lifestyle.hobbies?.length || lifestyle.interests?.length || lifestyle.languages?.length),
  );
}

export function Lifestyle({ lifestyle }: { lifestyle: NonNullable<ProfileDetail["lifestyle"]> }) {
  return (
    <div className="flex flex-col gap-5">
      {lifestyle.diet && <DetailList items={[{ label: "Diet", value: lifestyle.diet }]} />}
      <Tags label="Hobbies" values={lifestyle.hobbies} />
      <Tags label="Interests" values={lifestyle.interests} />
      <Tags label="Languages Known" values={lifestyle.languages} />
    </div>
  );
}
