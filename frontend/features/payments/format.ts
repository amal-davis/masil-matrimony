import type { BadgeTone } from "@/features/dashboard/components/ui";
import type { PurchaseStatus } from "@/features/dashboard/types";

const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

/** An API amount ("118000.00") for display: "₹1,18,000.00". Display only; never used to calculate. */
export function formatAmount(value: string | null | undefined): string {
  if (!value) return "—";
  const amount = Number(value);
  return Number.isFinite(amount) ? rupees.format(amount) : "—";
}

/** "18.00" → "18%". */
export function formatRate(value: string): string {
  const rate = Number(value);
  return Number.isFinite(rate) ? `${Number.isInteger(rate) ? rate : rate.toFixed(2)}%` : "—";
}

/** How each purchase status is shown: never "paid" unless the server says so. */
export const purchaseStatus: Record<PurchaseStatus, { label: string; tone: BadgeTone }> = {
  awaiting_payment: { label: "Awaiting payment", tone: "neutral" },
  authorized: { label: "Being confirmed", tone: "info" },
  paid: { label: "Paid", tone: "success" },
  failed: { label: "Payment failed", tone: "danger" },
  needs_review: { label: "Under review", tone: "info" },
  order_failed: { label: "Not started", tone: "neutral" },
};
