"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { useController, useForm, useWatch, type Control, type UseFormRegisterReturn } from "react-hook-form";

import { controlClasses, ErrorText, errorProps, Field, Select } from "@/components/ui/form-field";
import { SearchIcon } from "@/components/ui/icons";
import { RangeSlider, type RangeValue } from "@/components/ui/range-slider";
import { cn } from "@/lib/utils";

import {
  AGE_RANGE,
  communitiesFor,
  HEIGHT_RANGE_CM,
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
  formatRange,
  SEARCH_RESULTS_PATH,
  partnerSearchSchema,
  type PartnerSearchInput,
  type PartnerSearchValues,
} from "../schema";

// reset() treats `undefined` as "back to the initial value", so clear the bride/groom choice with "".
const NO_CHOICE = "" as PartnerSearchInput["lookingFor"];

// Phones: 2 tight columns, where short selects that sit next to each other in the form share a row
// (`cell`) and everything else takes the full width (`wide`), to keep the card short. Tablets: 2
// columns. lg: roomy rows of three, then the actions bar.
const grid = "grid grid-cols-2 gap-x-3 gap-y-4 md:gap-x-6 md:gap-y-6 lg:grid-cols-3 lg:gap-x-8 lg:gap-y-7";
const cell = "min-w-0";
const wide = "min-w-0 max-md:col-span-2";
// A select sharing a phone row: less padding, so its text has room beside the chevron.
const pairedSelect = "max-md:pr-8 max-md:pl-2.5";

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
    Boolean(
      initialValues?.maritalStatus ||
        initialValues?.motherTongue ||
        initialValues?.education ||
        initialValues?.occupation ||
        initialValues?.profileId,
    ),
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

  const [religion, ...more] = useWatch({
    control,
    name: ["religion", "maritalStatus", "motherTongue", "education", "occupation", "profileId"],
  });
  const communities = communitiesFor(religion ?? "");
  const moreCount = more.filter((value) => value?.trim()).length;

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

  const moreFields = (
    <>
      <Field
        id={fieldId("maritalStatus")}
        label="Marital status"
        error={errors.maritalStatus?.message}
        className={cell}
      >
        <Select
          id={fieldId("maritalStatus")}
          className={pairedSelect}
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
        className={cell}
      >
        <Select
          id={fieldId("motherTongue")}
          className={pairedSelect}
          {...errorProps(fieldId("motherTongue"), errors.motherTongue?.message)}
          {...register("motherTongue")}
        >
          <option value="">Any</option>
          <Options options={motherTongueOptions} />
        </Select>
      </Field>
      <TextFilter
        id={fieldId("education")}
        label="Education"
        placeholder="e.g. B.Tech, MBBS"
        error={errors.education?.message}
        field={register("education")}
      />
      <TextFilter
        id={fieldId("occupation")}
        label="Occupation"
        placeholder="e.g. Engineer, Teacher"
        error={errors.occupation?.message}
        field={register("occupation")}
      />
      <TextFilter
        id={fieldId("profileId")}
        label="Matrimony ID"
        placeholder="e.g. MM482913"
        error={errors.profileId?.message}
        field={register("profileId")}
      />
    </>
  );

  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-white p-4 shadow-[0_1px_2px_rgba(36,26,28,0.04),0_8px_24px_rgba(36,26,28,0.06)] sm:p-8 lg:p-10",
        className,
      )}
    >
      {title && (
        <div className="mb-5 flex flex-col gap-1.5 sm:mb-7 lg:mb-9">
          <Heading id={fieldId("title")} className="text-2xl font-semibold sm:text-3xl">
            {title}
          </Heading>
          {description && <p className="text-base text-ink-muted sm:text-lg">{description}</p>}
        </div>
      )}

      <form
        noValidate
        role="search"
        aria-labelledby={title ? fieldId("title") : undefined}
        aria-label={title ? undefined : "Partner search"}
        onSubmit={handleSubmit(onSubmit)}
      >
        <div className={grid}>
          <Field
            id={fieldId("lookingFor")}
            label="I am looking for a"
            error={errors.lookingFor?.message}
            className={wide}
          >
            <Select
              id={fieldId("lookingFor")}
              aria-required="true"
              {...errorProps(fieldId("lookingFor"), errors.lookingFor?.message)}
              {...register("lookingFor")}
            >
              <option value="">Bride or groom</option>
              <Options options={lookingForOptions} />
            </Select>
          </Field>

          <RangeFilter
            id={fieldId("age")}
            control={control}
            names={["ageMin", "ageMax"]}
            label="Age"
            thumbLabels={["Minimum age", "Maximum age"]}
            scale={AGE_RANGE}
            unit="yrs"
            spokenUnit="years"
            error={errors.ageMin?.message ?? errors.ageMax?.message}
          />

          <RangeFilter
            id={fieldId("height")}
            control={control}
            names={["heightMin", "heightMax"]}
            label="Height"
            thumbLabels={["Minimum height", "Maximum height"]}
            scale={HEIGHT_RANGE_CM}
            unit="cm"
            spokenUnit="centimetres"
            error={errors.heightMin?.message ?? errors.heightMax?.message}
          />

          <Field id={fieldId("religion")} label="Religion" error={errors.religion?.message} className={cell}>
            <Select
              id={fieldId("religion")}
              className={pairedSelect}
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
              className={pairedSelect}
              disabled={communities.length === 0}
              {...errorProps(fieldId("community"), errors.community?.message)}
              {...register("community")}
            >
              <option value="">
                {religion && communities.length === 0
                  ? "None listed"
                  : religion
                    ? "Any"
                    : "Pick religion"}
              </option>
              <Options options={communities} />
            </Select>
          </Field>

          <Field id={fieldId("location")} label="Location" error={errors.location?.message} className={wide}>
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
        </div>

        {/* Same columns as the grid above. Kept in the DOM while collapsed so selections survive toggling. */}
        <div id={fieldId("more")} hidden={!showMore} className={cn(grid, "mt-6 lg:mt-7")}>
          {/* The API enforces this (backend/apps/profiles/search.py ADVANCED_FILTERS); the note only says so up front. */}
          <p className="col-span-full text-sm text-ink-muted">
            Marital status, mother tongue, education and occupation are advanced filters, included with the Silver,
            Gold and Diamond memberships. Matrimony ID search is open to every member.
          </p>
          {moreFields}
        </div>

        <div className="mt-6 flex flex-col-reverse gap-2 border-t border-line pt-5 sm:mt-8 sm:flex-row sm:gap-4 sm:pt-6 sm:items-center sm:justify-between lg:mt-9 lg:pt-7">
          <div className="flex items-center justify-center gap-2 sm:-ml-3 sm:justify-start">
            <button
              type="button"
              aria-expanded={showMore}
              aria-controls={fieldId("more")}
              onClick={() => setShowMore((value) => !value)}
              className="inline-flex h-11 items-center gap-1.5 rounded-md px-3 text-[0.9375rem] font-medium text-wine-600 transition-colors hover:bg-wine-600/5 focus-visible:outline-wine-600 sm:h-12"
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
            <span aria-hidden="true" className="h-5 w-px bg-line" />
            <button
              type="button"
              onClick={() => reset({ ...emptyFilters, lookingFor: NO_CHOICE })}
              className="inline-flex h-11 items-center rounded-md px-3 text-[0.9375rem] font-medium text-ink-muted transition-colors hover:text-ink focus-visible:outline-wine-600 sm:h-12"
            >
              Clear all
            </button>
          </div>

          <button
            type="submit"
            disabled={navigating}
            className="inline-flex h-13 w-full items-center justify-center gap-2.5 rounded-md bg-wine-600 px-10 text-base font-medium whitespace-nowrap text-white transition-colors duration-200 hover:bg-wine-800 focus-visible:outline-wine-600 disabled:cursor-wait disabled:opacity-60 sm:w-auto sm:min-w-56"
          >
            <SearchIcon className="size-5" />
            {navigating ? "Searching…" : "Search profiles"}
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

/** A free-text filter. Pressing Enter submits the search, as in any form. */
function TextFilter({
  id,
  label,
  placeholder,
  error,
  field,
}: {
  id: string;
  label: string;
  placeholder: string;
  error?: string;
  field: UseFormRegisterReturn;
}) {
  return (
    <Field id={id} label={label} error={error} className={wide}>
      <input
        id={id}
        type="text"
        maxLength={60}
        autoComplete="off"
        placeholder={placeholder}
        className={controlClasses}
        {...errorProps(id, error)}
        {...field}
      />
    </Field>
  );
}

type RangeName = "ageMin" | "ageMax" | "heightMin" | "heightMax";

/**
 * A dual-thumb slider over a min/max pair of filters. A thumb at its end of the
 * scale means "no limit": that field stays "" and isn't sent, as with "Any" before.
 */
function RangeFilter({
  id,
  control,
  names: [minName, maxName],
  label,
  thumbLabels,
  scale,
  unit,
  spokenUnit,
  error,
}: {
  id: string;
  control: Control<PartnerSearchInput, unknown, PartnerSearchValues>;
  names: [RangeName, RangeName];
  label: string;
  thumbLabels: [string, string];
  scale: { min: number; max: number };
  unit: string;
  spokenUnit: string;
  error?: string;
}) {
  const { field: low } = useController({ control, name: minName });
  const { field: high } = useController({ control, name: maxName });
  const value: RangeValue = [low.value ? Number(low.value) : scale.min, high.value ? Number(high.value) : scale.max];

  const onChange = ([min, max]: RangeValue) => {
    low.onChange(min === scale.min ? "" : String(min));
    high.onChange(max === scale.max ? "" : String(max));
  };
  const valueText = (value: number, thumb: 0 | 1) =>
    thumb === 0 && value === scale.min
      ? "No minimum"
      : thumb === 1 && value === scale.max
        ? "No maximum"
        : `${value} ${spokenUnit}`;
  const text = formatRange(low.value, high.value, unit);

  return (
    <div className={wide}>
      <RangeSlider
        id={id}
        label={label}
        min={scale.min}
        max={scale.max}
        value={value}
        onChange={onChange}
        onBlur={low.onBlur}
        thumbLabels={thumbLabels}
        valueText={valueText}
        display={text ? text.charAt(0).toUpperCase() + text.slice(1) : "Any"}
        invalid={Boolean(error)}
        describedBy={error ? `${id}-error` : undefined}
      />
      <ErrorText id={`${id}-error`} message={error} />
    </div>
  );
}
