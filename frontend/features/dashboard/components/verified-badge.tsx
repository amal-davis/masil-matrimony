import { VerifiedIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/** Shown only when the API says Massil staff verified the member's identity (`verified: true`). */
export function VerifiedBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-semibold text-success ring-1 ring-success/30 ring-inset",
        className,
      )}
    >
      <VerifiedIcon className="size-3.5" aria-hidden="true" />
      Verified
    </span>
  );
}
