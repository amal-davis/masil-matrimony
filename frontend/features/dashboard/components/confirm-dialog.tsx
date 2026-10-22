"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { dangerButton, primaryButton, secondaryButton } from "./ui";

/**
 * A modal confirmation for consequential actions. Uses the native <dialog>:
 * focus moves into it and stays there, Escape closes it, and the page behind
 * is inert. Fits narrow screens.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-xl border border-line bg-white p-0 text-ink shadow-[0_12px_32px_rgba(36,26,28,0.18)] backdrop:bg-wine-900/50"
    >
      <div className="p-5 sm:p-6">
        <h2 id={titleId} className="text-lg font-semibold sm:text-xl">
          {title}
        </h2>
        {children && <div className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">{children}</div>}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onCancel} disabled={busy} className={secondaryButton}>
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={cn(tone === "danger" ? dangerButton : primaryButton)}
          >
            {busy ? "Please wait…" : confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
