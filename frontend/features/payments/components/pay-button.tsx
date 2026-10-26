"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";

import { startPurchase, verifyPayment } from "@/features/dashboard/actions";
import { Notice, primaryButton } from "@/features/dashboard/components/ui";
import type { CheckoutOptions } from "@/features/dashboard/types";
import { cn } from "@/lib/utils";

import { loadRazorpay, openCheckout } from "../razorpay-checkout";

type Phase = "idle" | "starting" | "open" | "verifying";
type Message = { tone: "info" | "danger"; text: string; reference?: string } | null;

const LABEL: Record<Phase, string> = {
  idle: "",
  starting: "Preparing secure payment…",
  open: "Payment window open…",
  verifying: "Confirming your payment…",
};

/**
 * Pay for a package (`packageCode`: the API creates or resumes the order) or
 * for an existing unpaid purchase (`existing`). Afterwards the member is always
 * taken to the purchase page, which shows what the server confirmed: this
 * component never declares a payment successful itself.
 */
export function PayButton({
  packageCode,
  existing,
  label,
  requireConsent = false,
  className,
}: {
  packageCode?: string;
  existing?: { reference: string; checkout: CheckoutOptions };
  label: string;
  /** Ask the member to accept the terms and refund policy first. */
  requireConsent?: boolean;
  className?: string;
}) {
  const id = useId();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<Message>(null);
  const [consent, setConsent] = useState(!requireConsent);
  const busy = useRef(false); // guards double clicks before React re-renders

  const pay = async () => {
    if (busy.current || phase !== "idle") return;
    if (!consent) {
      setMessage({ tone: "danger", text: "Please accept the terms and refund policy to continue." });
      return;
    }
    busy.current = true;
    setMessage(null);
    setPhase("starting");
    try {
      let reference = existing?.reference;
      let checkout = existing?.checkout;
      if (!reference || !checkout) {
        const started = await startPurchase(packageCode ?? "");
        if (!started.ok) {
          setMessage({ tone: "danger", text: started.message });
          return;
        }
        reference = started.data.purchase.reference;
        checkout = started.data.checkout;
      }

      try {
        await loadRazorpay();
      } catch {
        setMessage({
          tone: "danger",
          text: "The payment window couldn't be loaded. Please check your connection and try again. Nothing was charged.",
          reference,
        });
        return;
      }

      setPhase("open");
      const outcome = await openCheckout(checkout, (failure) =>
        setMessage({ tone: "danger", text: `That payment attempt failed: ${failure} You can try again in the payment window.` }),
      );
      if (outcome.kind === "dismissed") {
        setMessage({
          tone: "info",
          text: "The payment window was closed before a payment was completed. You can try again whenever you're ready.",
          reference,
        });
        return;
      }

      setPhase("verifying");
      const verified = await verifyPayment(reference, outcome.response);
      if (!verified.ok && verified.status === 400) {
        setMessage({ tone: "danger", text: verified.message, reference });
        return;
      }
      // The purchase page shows the server's answer: paid, still being confirmed, or failed.
      router.push(`/dashboard/membership/purchases/${reference}?from=checkout`);
    } finally {
      busy.current = false;
      setPhase((current) => (current === "verifying" ? current : "idle"));
    }
  };

  const working = phase !== "idle";

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {requireConsent && (
        <label htmlFor={`${id}-consent`} className="flex items-start gap-3 text-[0.9375rem] text-ink">
          <input
            id={`${id}-consent`}
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            disabled={working}
            className="mt-0.5 size-5 shrink-0 accent-wine-600"
          />
          <span>
            I agree to the{" "}
            <Link href="/terms-and-conditions" className="font-medium text-wine-600 underline underline-offset-4">
              Terms of Use
            </Link>{" "}
            and the{" "}
            <Link href="/refund-policy" className="font-medium text-wine-600 underline underline-offset-4">
              Refund &amp; Cancellation Policy
            </Link>
            .
          </span>
        </label>
      )}

      <div role="status" aria-live="polite">
        {message && (
          <Notice tone={message.tone === "danger" ? "danger" : "info"}>
            {message.text}
            {message.reference && (
              <>
                {" "}
                <Link
                  href={`/dashboard/membership/purchases/${message.reference}`}
                  className="font-medium text-wine-600 underline underline-offset-4"
                >
                  View this purchase
                </Link>
              </>
            )}
          </Notice>
        )}
      </div>

      <button type="button" onClick={pay} disabled={working} aria-busy={working} className={cn(primaryButton, "w-full")}>
        {working ? LABEL[phase] : label}
      </button>
    </div>
  );
}
