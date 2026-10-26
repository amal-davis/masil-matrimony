"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { refreshPaymentStatus } from "@/features/dashboard/actions";
import { Notice, secondaryButton } from "@/features/dashboard/components/ui";
import { cn } from "@/lib/utils";

/**
 * "Check payment status": the API asks Razorpay about the order again and the
 * page re-renders with the server's answer. With `autoCheckAfterMs` it also
 * checks once by itself (just after returning from Razorpay Checkout, when a
 * webhook may still be on its way).
 */
export function CheckStatusButton({ reference, autoCheckAfterMs }: { reference: string; autoCheckAfterMs?: number }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string>();
  const autoChecked = useRef(false);

  const check = () =>
    startTransition(async () => {
      setError(undefined);
      const result = await refreshPaymentStatus(reference);
      if (!result.ok) setError(result.message);
    });

  useEffect(() => {
    if (!autoCheckAfterMs || autoChecked.current) return;
    autoChecked.current = true;
    const timer = window.setTimeout(check, autoCheckAfterMs);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, [autoCheckAfterMs]);

  return (
    <div className="flex flex-col gap-3">
      <button type="button" onClick={check} disabled={pending} aria-busy={pending} className={cn(secondaryButton, "w-full")}>
        {pending ? "Checking with Razorpay…" : "Check payment status"}
      </button>
      <div role="status" aria-live="polite">
        {error && <Notice tone="danger">{error}</Notice>}
      </div>
    </div>
  );
}
