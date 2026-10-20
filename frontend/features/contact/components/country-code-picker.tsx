"use client";

import type { CountryCode } from "libphonenumber-js";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { SearchIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import { COUNTRY_OPTIONS } from "../schema";

type CountryOption = (typeof COUNTRY_OPTIONS)[number];

// Flags are static files in public/flags (see scripts/copy-flags.mjs). Plain <img> paths
// don't get the GitHub Pages base path added automatically, so add it here.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** Lower-case and drop accents, so "aland" finds "Åland Islands". */
const fold = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

const SEARCH_KEYS = new Map(COUNTRY_OPTIONS.map((option) => [option.code, fold(option.name)]));

/** Match by country name, ISO code ("ae") or calling code ("971" or "+971"). */
function filterCountries(query: string): CountryOption[] {
  const q = fold(query.trim());
  if (!q) return COUNTRY_OPTIONS;
  const digits = q.replace(/^\+/, "");
  if (/^\d+$/.test(digits)) return COUNTRY_OPTIONS.filter((option) => option.dialCode.slice(1).startsWith(digits));
  return COUNTRY_OPTIONS.filter(
    (option) => SEARCH_KEYS.get(option.code)!.includes(q) || option.code.toLowerCase() === q,
  );
}

function Flag({ code, className }: { code: CountryCode; className?: string }) {
  return (
    // An SVG flag needs no optimisation, so next/image would add nothing here.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${BASE_PATH}/flags/${code}.svg`}
      alt=""
      width={24}
      height={16}
      loading="lazy"
      decoding="async"
      className={cn("h-4 w-6 shrink-0 rounded-[2px] object-cover ring-1 ring-ink/10", className)}
    />
  );
}

/**
 * Country calling-code picker with flags: a button showing the chosen flag and
 * code, opening a searchable list. Follows the ARIA combobox pattern: focus
 * stays in the search box while arrow keys move through the list.
 */
export function CountryCodePicker({
  value,
  onChange,
  onBlur,
}: {
  value: CountryCode;
  onChange: (code: CountryCode) => void;
  onBlur?: () => void;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selected = COUNTRY_OPTIONS.find((option) => option.code === value) ?? COUNTRY_OPTIONS[0];
  const results = useMemo(() => filterCountries(query), [query]);

  const openList = () => {
    setQuery("");
    setActive(Math.max(0, COUNTRY_OPTIONS.indexOf(selected)));
    setOpen(true);
  };

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
    onBlur?.();
  };

  const choose = (option: CountryOption) => {
    onChange(option.code);
    close(true);
  };

  // Close when the visitor clicks or taps anywhere outside the picker.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `close` only reads refs and props
  }, [open]);

  // Keep the highlighted option visible while moving through the list.
  useEffect(() => {
    if (open) listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const onSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const last = results.length - 1;
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActive((index) => Math.min(index + 1, last));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActive((index) => Math.max(index - 1, 0));
        break;
      case "PageDown":
        event.preventDefault();
        setActive((index) => Math.min(index + 8, last));
        break;
      case "PageUp":
        event.preventDefault();
        setActive((index) => Math.max(index - 8, 0));
        break;
      case "Enter":
        event.preventDefault();
        if (results[active]) choose(results[active]);
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        close(false);
        break;
    }
  };

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={`Country code: ${selected.name} ${selected.dialCode}`}
        onClick={() => (open ? close(true) : openList())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            openList();
          }
        }}
        className={cn(
          "flex h-12 items-center gap-2 rounded-md border border-field-line bg-white pr-2.5 pl-3 text-base text-ink transition-colors hover:border-wine-600 focus-visible:border-wine-600 focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-wine-600",
          open && "border-wine-600",
        )}
      >
        <Flag code={selected.code} />
        <span className="tabular-nums">{selected.dialCode}</span>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={cn("size-4 shrink-0 text-ink-muted transition-transform", open && "rotate-180")}
        >
          <path
            fillRule="evenodd"
            d="M5.22 7.72a.75.75 0 0 1 1.06 0L10 11.44l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.78a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 z-30 mt-1.5 w-[min(20rem,calc(100vw-3rem))] overflow-hidden rounded-lg border border-line bg-white shadow-[0_12px_32px_rgba(36,26,28,0.14)]">
          <div className="relative border-b border-line p-2">
            <SearchIcon
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-4.5 size-4 -translate-y-1/2 text-ink-muted"
            />
            <input
              type="text"
              role="combobox"
              aria-label="Search country or code"
              aria-expanded="true"
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={results[active] ? `${id}-${results[active].code}` : undefined}
              placeholder="Search country or code"
              autoComplete="off"
              spellCheck={false}
              autoFocus
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              onKeyDown={onSearchKeyDown}
              className="h-10 w-full rounded-md border border-field-line bg-white pr-3 pl-9 text-base text-ink placeholder:text-ink-muted/70 focus:border-wine-600 focus:outline-2 focus:-outline-offset-1 focus:outline-wine-600"
            />
          </div>

          <ul ref={listRef} id={listId} role="listbox" aria-label="Country codes" className="max-h-64 overflow-y-auto py-1">
            {results.map((option, index) => {
              const isSelected = option.code === selected.code;
              return (
                <li
                  key={option.code}
                  id={`${id}-${option.code}`}
                  role="option"
                  aria-selected={isSelected}
                  data-index={index}
                  // Keep focus in the search box; the click below makes the choice.
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActive(index)}
                  onClick={() => choose(option)}
                  className={cn(
                    "flex min-h-11 cursor-pointer items-center gap-3 px-3 text-[0.9375rem] text-ink",
                    index === active && "bg-brand-50",
                    isSelected && "font-medium text-wine-600",
                  )}
                >
                  <Flag code={option.code} />
                  <span className="min-w-0 flex-1 truncate">{option.name}</span>
                  <span className="shrink-0 text-ink-muted tabular-nums">{option.dialCode}</span>
                </li>
              );
            })}
          </ul>
          {results.length === 0 && (
            <p role="status" className="px-3 py-4 text-[0.9375rem] text-ink-muted">
              No matching country.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
