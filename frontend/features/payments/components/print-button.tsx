"use client";

import { secondaryButton } from "@/features/dashboard/components/ui";
import { cn } from "@/lib/utils";

/** Opens the browser's print dialog, where "Save as PDF" downloads the receipt. */
export function PrintButton({ className }: { className?: string }) {
  return (
    <button type="button" onClick={() => window.print()} className={cn(secondaryButton, "print:hidden", className)}>
      Print or save as PDF
    </button>
  );
}
