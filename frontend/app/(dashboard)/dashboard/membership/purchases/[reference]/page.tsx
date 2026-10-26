import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Badge, Card, Notice, PageHeader, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { getPurchase } from "@/features/dashboard/server-api";
import type { Purchase } from "@/features/dashboard/types";
import { CheckStatusButton } from "@/features/payments/components/check-status-button";
import { PayButton } from "@/features/payments/components/pay-button";
import { formatAmount, formatRate, purchaseStatus } from "@/features/payments/format";

export const metadata: Metadata = { title: "Purchase", robots: { index: false, follow: false } };

/**
 * Not an instant navigation, by design: the URL segment is only known per request
 * (the dashboard shell reads it with usePathname for its navigation), and the page
 * waits for this member's own data from the API before it can show anything.
 */
export const instant = false;

/** What the member is told for each status. Only "paid" says the membership is active. */
function statusMessage(purchase: Purchase): { title: string; body: ReactNode; tone: "success" | "info" | "danger" } {
  switch (purchase.status) {
    case "paid":
      return {
        tone: "success",
        title: "Payment received. Your membership is active.",
        body: purchase.membership
          ? `${purchase.package_name} is valid from ${formatDate(purchase.membership.starts_at)} until ${formatDate(purchase.membership.ends_at)}.`
          : `${purchase.package_name} is active.`,
      };
    case "authorized":
      return {
        tone: "info",
        title: "Your bank has approved the payment. We're waiting for Razorpay to confirm it.",
        body: "This usually takes a few minutes. Your membership is activated as soon as it's confirmed. If it isn't, Razorpay returns the money automatically.",
      };
    case "failed":
      return {
        tone: "danger",
        title: "The payment didn't go through.",
        body: purchase.failure_reason || "No money was taken for this attempt. You can try again.",
      };
    case "needs_review":
      return {
        tone: "info",
        title: "We're checking this payment.",
        body: "Something about this payment needs a manual check before your membership can be activated. Our team will contact you; you can also contact us with the purchase reference below.",
      };
    case "order_failed":
      return {
        tone: "danger",
        title: "The payment couldn't be started.",
        body: "Nothing was charged. Please try again from the membership page.",
      };
    default:
      return {
        tone: "info",
        title: "We haven't received a payment for this purchase yet.",
        body: purchase.confirmation_pending
          ? "Your payment is being confirmed with Razorpay. Check the status again in a moment."
          : "If you've just paid, check the status in a moment. Otherwise you can pay now.",
      };
  }
}

export default async function PurchasePage({ params, searchParams }: PageProps<"/dashboard/membership/purchases/[reference]">) {
  const [{ reference }, query] = await Promise.all([params, searchParams]);
  const purchase = await getPurchase(reference);
  if (!purchase) notFound();
  const message = statusMessage(purchase);
  const status = purchaseStatus[purchase.status];
  const fromCheckout = query.from === "checkout";

  return (
    <>
      <PageHeader
        title={purchase.package_name}
        description={`Purchase ${purchase.reference}`}
        actions={
          <Link href="/dashboard/membership" className={secondaryButton}>
            Back to membership
          </Link>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-6">
          <Notice tone={message.tone} role="status">
            <strong className="block font-semibold">{message.title}</strong>
            <span className="mt-1 block">{message.body}</span>
          </Notice>

          <Card title="Purchase details" titleId="details-title" actions={<Badge tone={status.tone}>{status.label}</Badge>}>
            <dl className="grid gap-x-6 gap-y-3 text-[0.9375rem] sm:grid-cols-2">
              <div>
                <dt className="text-sm text-ink-muted">Package</dt>
                <dd className="font-medium">{purchase.package_name} · {purchase.validity_months} months</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Amount</dt>
                <dd className="font-medium tabular-nums">
                  {formatAmount(purchase.amounts.total)}
                  <span className="block text-sm font-normal text-ink-muted">
                    {formatAmount(purchase.amounts.base)} + GST {formatRate(purchase.amounts.gst_rate)} {formatAmount(purchase.amounts.gst)}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Started</dt>
                <dd className="font-medium">{formatDate(purchase.created_at)}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Paid</dt>
                <dd className="font-medium">{purchase.paid_at ? formatDate(purchase.paid_at) : "—"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-sm text-ink-muted">References</dt>
                <dd className="text-sm break-all">
                  Purchase {purchase.reference}
                  {purchase.razorpay_payment_id && <> · Razorpay payment {purchase.razorpay_payment_id}</>}
                </dd>
              </div>
            </dl>
            {purchase.test_mode && <p className="mt-4 text-sm text-ink-muted">Test mode: no real money was charged.</p>}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          {purchase.receipt && (
            <Card title="Receipt" titleId="receipt-title">
              <p className="text-[0.9375rem] text-ink-muted">
                Receipt {purchase.receipt.number}. We email it to your registered address once the payment is confirmed.
              </p>
              <Link href={`/dashboard/membership/receipts/${purchase.receipt.id}`} className={`${primaryButton} mt-4 w-full`}>
                View &amp; print receipt
              </Link>
            </Card>
          )}

          {(purchase.can_pay || purchase.can_check_status) && (
            <Card title="Next step" titleId="next-title">
              <div className="flex flex-col gap-4">
                {purchase.can_pay && purchase.checkout && (
                  <PayButton
                    existing={{ reference: purchase.reference, checkout: purchase.checkout }}
                    label={purchase.status === "failed" ? "Try the payment again" : `Pay ${formatAmount(purchase.amounts.total)} now`}
                  />
                )}
                {purchase.can_check_status && (
                  <CheckStatusButton reference={purchase.reference} autoCheckAfterMs={fromCheckout ? 4000 : undefined} />
                )}
              </div>
            </Card>
          )}

          <Card title="Need help?" titleId="help-title">
            <p className="text-[0.9375rem] text-ink-muted">
              Contact us with the purchase reference <strong className="font-semibold text-ink">{purchase.reference}</strong>.
            </p>
            <Link href="/contact" className={`${secondaryButton} mt-4 w-full`}>
              Contact us
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
