"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition, type ReactNode } from "react";
import { useForm, useWatch, type UseFormRegisterReturn } from "react-hook-form";

import { ErrorText, errorProps, Field, SegmentedOption, Select } from "@/components/ui/form-field";
import { SearchIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import {
  ageOptions,
  communitiesFor,
  heightOptions,
  locationGroups,
  lookingForOptions,
  maritalStatusOptions,
  motherTongueOptions,
  religionOptions,
  type Option,
} from "../options";
import {
  emptyFilters,
  filtersToQuery,
  SEARCH_RESULTS_PATH,
  partnerSearchSchema,
  type PartnerSearchInput,
  type PartnerSearchValues,
} from "../schema";

// reset() treats `undefined` as "back to the initial value", so clear the radio group with "".
const NO_CHOICE = "" as PartnerSearchInput["lookingFor"];

// Phones: 1 column. Tablets: 2. lg: 3 per row. xl: the main filters and Search share one row.
const grid =
  "grid grid-cols-1 gap-x-5 gap-y-5 md:grid-cols-2 lg:grid-cols-6 xl:grid-cols-[minmax(0,8.75rem)_minmax(0,10rem)_minmax(0,12.5rem)_minmax(0,1fr)_minmax(0,1.2fr)_auto] xl:gap-x-4";
const cell = "min-w-0 lg:col-span-2 xl:col-span-1";
const moreCell = "min-w-0 lg:col-span-2 xl:col-span-1";

type PartnerSearchFilterProps = {
  /** Card heading and supporting text; omit when the page already has a heading. */
  title?: string;
  description?: string;
  headingLevel?: "h1" | "h2";
  initialValues?: Partial<PartnerSearchInput>;
  className?: string;
};

/**
 * Partner search card. Submitting navigates to `/search?gender=…&age_min=…`
 * (client-side), which the search page parses with `filtersFromQuery`.
 */
export function PartnerSearchFilter({
  title,
  description,
  headingLevel: Heading = "h2",
  initialValues,
  className,
}: PartnerSearchFilterProps) {
  const id = useId();
  const fieldId = (name: string) => `${id}-${name}`;
  const router = useRouter();
  const [navigating, startNavigation] = useTransition();
  const [showMore, setShowMore] = useState(
    Boolean(initialValues?.location || initialValues?.maritalStatus || initialValues?.motherTongue),
  );

  const {
    register,
    handleSubmit,
    control,
    getValues,
    setValue,
    reset,
    formState: { errors },
  } = useForm<PartnerSearchInput, unknown, PartnerSearchValues>({
    resolver: zodResolver(partnerSearchSchema),
    mode: "onTouched",
    defaultValues: { ...emptyFilters, ...initialValues },
  });

  const [religion, location, maritalStatus, motherTongue] = useWatch({
    control,
    name: ["religion", "location", "maritalStatus", "motherTongue"],
  });
  const communities = communitiesFor(religion ?? "");
  const moreCount = [location, maritalStatus, motherTongue].filter(Boolean).length;

  const onSubmit = (values: PartnerSearchValues) => {
    startNavigation(() => router.push(`${SEARCH_RESULTS_PATH}?${filtersToQuery(values)}`));
  };

  const religionField = register("religion", {
    onChange: (event) => {
      // Keep the community only if it still belongs to the newly chosen religion.
      const stillValid = communitiesFor(event.target.value).some((c) => c.value === getValues("community"));
      if (!stillValid) setValue("community", "", { shouldValidate: true });
    },
  });

  // Rendered twice: beside the heading from lg, and next to the Search button below lg.
  const toolbar = (className: string) => (
    <div className={cn("items-center gap-1", className)}>
      <button
        type="button"
        aria-expanded={showMore}
        aria-controls={fieldId("more")}
        onClick={() => setShowMore((value) => !value)}
        className="inline-flex h-11 items-center gap-1.5 rounded-md px-3 text-[0.9375rem] font-medium text-wine-600 transition-colors hover:bg-wine-600/5 focus-visible:outline-wine-600"
      >
        {showMore ? "Fewer filters" : "More filters"}
        {moreCount > 0 && (
          <span className="inline-flex size-5 items-center justify-center rounded-full bg-wine-600 text-xs text-white">
            {moreCount}
            <span className="sr-only"> selected</span>
          </span>
        )}
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={cn("size-5 transition-transform duration-200", showMore && "rotate-180")}
        >
          <path
            fillRule="evenodd"
            d="M5.22 7.72a.75.75 0 0 1 1.06 0L10 11.44l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.78a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      <button
        type="button"
        onClick={() => reset({ ...emptyFilters, lookingFor: NO_CHOICE })}
        className="inline-flex h-11 items-center rounded-md px-3 text-[0.9375rem] font-medium text-ink-muted transition-colors hover:text-ink focus-visible:outline-wine-600"
      >
        Clear
      </button>
    </div>
  );

  return (
    <div
      className={cn(
        "rounded-xl border border-line bg-white p-5 shadow-[0_1px_2px_rgba(36,26,28,0.04),0_8px_24px_rgba(36,26,28,0.06)] sm:p-7 lg:p-8",
        className,
      )}
    >
      <div
        className={cn(
          "lg:flex lg:items-end lg:justify-between lg:gap-6",
          title ? "mb-6 lg:mb-7" : "lg:-mt-2 lg:mb-3",
        )}
      >
        {title && (
          <div className="flex flex-col gap-1">
            <Heading id={fieldId("title")} className="text-2xl font-semibold sm:text-3xl">
              {title}
            </Heading>
            {description && <p className="text-base text-ink-muted">{description}</p>}
          </div>
        )}
        {toolbar("ml-auto hidden shrink-0 lg:flex lg:-mr-3")}
      </div>

      <form
        noValidate
        role="search"
        aria-labelledby={title ? fieldId("title") : undefined}
        aria-label={title ? undefined : "Partner search"}
        onSubmit={handleSubmit(onSubmit)}
        className={grid}
      >
        <fieldset
          className={cell}
          aria-describedby={errors.lookingFor ? `${fieldId("lookingFor")}-error` : undefined}
        >
          <legend className="text-sm font-medium text-ink">I am looking for a</legend>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {lookingForOptions.map((option) => (
              <SegmentedOption
                key={option.value}
                value={option.value}
                label={option.label}
                invalid={Boolean(errors.lookingFor)}
                {...register("lookingFor")}
              />
            ))}
          </div>
          <ErrorText id={`${fieldId("lookingFor")}-error`} message={errors.lookingFor?.message} />
        </fieldset>

        <RangeField
          id={fieldId("age")}
          legend="Age (years)"
          className={cell}
          options={ageOptions}
          min={{ label: "Minimum age", field: register("ageMin"), error: errors.ageMin?.message }}
          max={{ label: "Maximum age", field: register("ageMax"), error: errors.ageMax?.message }}
        />

        <RangeField
          id={fieldId("height")}
          legend="Height"
          className={cell}
          options={heightOptions}
          min={{ label: "Minimum height", field: register("heightMin"), error: errors.heightMin?.message }}
          max={{ label: "Maximum height", field: register("heightMax"), error: errors.heightMax?.message }}
        />

        <Field id={fieldId("religion")} label="Religion" error={errors.religion?.message} className={cell}>
          <Select
            id={fieldId("religion")}
            {...errorProps(fieldId("religion"), errors.religion?.message)}
            {...religionField}
          >
            <option value="">Any</option>
            <Options options={religionOptions} />
          </Select>
        </Field>

        <Field id={fieldId("community")} label="Community" error={errors.community?.message} className={cell}>
          <Select
            id={fieldId("community")}
            disabled={communities.length === 0}
            {...errorProps(fieldId("community"), errors.community?.message)}
            {...register("community")}
          >
            <option value="">
              {religion && communities.length === 0 ? "None listed" : religion ? "Any" : "Religion first"}
            </option>
            <Options options={communities} />
          </Select>
        </Field>

        {/* Kept in the DOM while collapsed so selections survive toggling. */}
        <div
          id={fieldId("more")}
          hidden={!showMore}
          className="grid grid-cols-1 gap-x-5 gap-y-5 md:col-span-2 md:grid-cols-2 lg:order-last lg:col-span-6 lg:grid-cols-6 xl:col-span-full xl:grid-cols-4 xl:gap-x-4"
        >
          <Field
            id={fieldId("location")}
            label="Location"
            error={errors.location?.message}
            className={moreCell}
          >
            <Select
              id={fieldId("location")}
              {...errorProps(fieldId("location"), errors.location?.message)}
              {...register("location")}
            >
              <option value="">Anywhere</option>
              {locationGroups.map((group) => (
                <optgroup key={group.label} label={group.label}>
                  <Options options={group.options} />
                </optgroup>
              ))}
            </Select>
          </Field>
          <Field
            id={fieldId("maritalStatus")}
            label="Marital status"
            error={errors.maritalStatus?.message}
            className={moreCell}
          >
            <Select
              id={fieldId("maritalStatus")}
              {...errorProps(fieldId("maritalStatus"), errors.maritalStatus?.message)}
              {...register("maritalStatus")}
            >
              <option value="">Any</option>
              <Options options={maritalStatusOptions} />
            </Select>
          </Field>
          <Field
            id={fieldId("motherTongue")}
            label="Mother tongue"
            error={errors.motherTongue?.message}
            className={moreCell}
          >
            <Select
              id={fieldId("motherTongue")}
              {...errorProps(fieldId("motherTongue"), errors.motherTongue?.message)}
              {...register("motherTongue")}
            >
              <option value="">Any</option>
              <Options options={motherTongueOptions} />
            </Select>
          </Field>
        </div>

        <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center md:justify-between lg:col-span-2 lg:self-start lg:pt-[1.625rem] xl:col-span-1">
          {toolbar("flex justify-center md:-ml-3 lg:hidden")}
          <button
            type="submit"
            disabled={navigating}
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-wine-600 px-8 text-base font-medium whitespace-nowrap text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-wait disabled:opacity-60 md:w-auto md:min-w-44 lg:w-full xl:min-w-0 xl:px-6"
          >
            <SearchIcon className="size-5" />
            {navigating ? "Searching…" : "Search"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Options({ options }: { options: readonly Option[] }) {
  return options.map((option) => (
    <option key={option.value} value={option.value}>
      {option.label}
    </option>
  ));
}

type RangeEnd = { label: string; field: UseFormRegisterReturn; error?: string };

/** A labelled pair of min/max selects. Errors from either end show below the pair. */
function RangeField({
  id,
  legend,
  options,
  min,
  max,
  className,
}: {
  id: string;
  legend: ReactNode;
  options: readonly Option[];
  min: RangeEnd;
  max: RangeEnd;
  className?: string;
}) {
  const error = min.error ?? max.error;
  return (
    <fieldset className={className} aria-describedby={error ? `${id}-error` : undefined}>
      <legend className="text-sm font-medium text-ink">{legend}</legend>
      <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1.5">
        <Select compact aria-label={min.label} aria-invalid={min.error ? true : undefined} {...min.field}>
          <option value="">Any</option>
          <Options options={options} />
        </Select>
        <span aria-hidden="true" className="text-sm text-ink-muted">
          to
        </span>
        <Select compact aria-label={max.label} aria-invalid={max.error ? true : undefined} {...max.field}>
          <option value="">Any</option>
          <Options options={options} />
        </Select>
      </div>
      <ErrorText id={`${id}-error`} message={error} />
    </fieldset>
  );
}
