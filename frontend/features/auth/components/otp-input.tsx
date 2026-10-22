"use client";

import { useState, type ComponentProps, type Ref } from "react";

import { cn } from "@/lib/utils";

type OtpInputProps = Omit<ComponentProps<"input">, "value" | "onChange" | "ref"> & {
  length: number;
  value: string;
  onChange: (value: string) => void;
  inputRef?: Ref<HTMLInputElement>;
};

/**
 * A one-time-code field drawn as one box per digit. It is a single real
 * <input>, so pasting the whole code, SMS autofill (autocomplete="one-time-code"),
 * keyboard editing and screen readers all work as for any text field; the
 * boxes are only a picture of its value.
 */
export function OtpInput({ length, value, onChange, inputRef, className, onFocus, onBlur, ...props }: OtpInputProps) {
  const [focused, setFocused] = useState(false);
  const active = Math.min(value.length, length - 1);
  const invalid = props["aria-invalid"] === true || props["aria-invalid"] === "true";

  return (
    <div className={cn("relative", className)}>
      <div
        aria-hidden="true"
        className="grid gap-2 sm:gap-3"
        style={{ gridTemplateColumns: `repeat(${length}, minmax(0, 1fr))` }}
      >
        {Array.from({ length }, (_, index) => (
          <span
            key={index}
            className={cn(
              "flex h-14 items-center justify-center rounded-md border bg-white text-2xl font-semibold text-ink tabular-nums transition-colors sm:h-16",
              invalid ? "border-danger" : "border-field-line",
              focused && index === active && "border-wine-600 outline-2 -outline-offset-1 outline-wine-600",
              props.disabled && "border-line bg-surface-muted text-ink-muted",
            )}
          >
            {value[index] ?? ""}
          </span>
        ))}
      </div>
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        spellCheck={false}
        value={value}
        // Keep only digits, so a pasted "123 456" or "123-456" still fills every box. No maxLength:
        // the browser would cut the pasted text to `length` characters before the spaces are removed.
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, length))}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        // Laid over the boxes: taps anywhere on them focus the field. Its own text and caret are hidden.
        className="absolute inset-0 size-full rounded-md bg-transparent text-base text-transparent caret-transparent outline-none selection:bg-transparent disabled:cursor-not-allowed"
        {...props}
      />
    </div>
  );
}
