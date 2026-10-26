import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, Notice, PageHeader, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";
import { getCheckoutQuote } from "@/features/dashboard/server-api";
import { maskPhoneNumber } from "@/features/auth/schema";
import { PayButton } from "@/features/payments/components/pay-button";
import { formatAmount, formatRate } from "@/features/payments/format";
import { validityLabel } from "@/features/packages/packages";

export const metadata: Metadata = { title: "Checkout", robots: { index: false, follow: false } };

/**
 * Not an instant navigation, by design: the URL segment is only known per request
 * (the dashboard shell reads it with usePathname for its navigation), and the page
 * waits for this member's own data from the API before it can show anything.
 */
export const instant = false;

/** What to offer when the API says this member can't buy the package online right now. */
const BLOCKED_ACTION: Record<string, { href: string; label: string }> = {
  email_required: { href: "/dashboard/settings#email", label: "Add my email address" },
  membership_active: { href: "/dashboard/membership", label: "View my membership" },
};

/**
 * Checkout for one package. Every figure comes from the API
 * (GET /payments/checkout/<code>/), which takes it from the package itself;
 * the page only displays it. Paying sends nothing but the package code.
 */
export default async function CheckoutPage({ params }: PageProps<"/dashboard/membership/checkout/[code]">) {
  const { code } = await params;
  const quote = await getCheckoutQuote(code);
  if (!quote) notFound();
  const { price, customer } = quote;
  const action = quote.blocked ? BLOCKED_ACTION[quote.blocked.code] : undefined;

  return (
    <>
      <PageHeader
        title="Checkout"
        description={`${quote.package.name} · ${validityLabel(quote.package.validity_months)}`}
        actions={
          <Link href="/dashboard/membership" className={secondaryButton}>
            Back to membership
          </Link>
        }
      />

      {quote.test_mode && (
        <Notice className="mb-6">
          <strong className="font-semibold">Test mode.</strong> Payments use Razorpay test keys: no real money is charged.
          Use Razorpay&apos;s test cards or UPI IDs.
        </Notice>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-6">
          <Card title="Order summary" titleId="summary-title">
            <p className="text-lg font-semibold">{quote.package.name}</p>
            <p className="mt-1 text-[0.9375rem] text-ink-muted">{quote.package.description}</p>
            {price ? (
              <dl className="mt-5 flex flex-col gap-2.5 border-t border-line pt-4 text-[0.9375rem]">
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-muted">{quote.package.fee_label}</dt>
                  <dd className="tabular-nums">{formatAmount(price.base)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-muted">GST ({formatRate(price.gst_rate)})</dt>
                  <dd className="tabular-nums">{formatAmount(price.gst)}</dd>
                </div>
                <div className="flex justify-between gap-4 border-t border-line pt-3 text-lg font-semibold">
                  <dt>Total payable</dt>
                  <dd className="tabular-nums">{formatAmount(price.total)}</dd>
                </div>
                <p className="text-sm text-ink-muted">
                  Validity: {validityLabel(quote.package.validity_months)} from activation. Amounts in Indian rupees.
                </p>
              </dl>
            ) : (
              <p className="mt-5 border-t border-line pt-4 text-[0.9375rem] text-ink-muted">
                The total including GST isn&apos;t confirmed for this package yet.
              </p>
            )}
          </Card>

          <Card title={quote.package.terms.title} titleId="terms-title">
            <p className="text-[0.9375rem] whitespace-pre-line text-ink-muted">{quote.package.terms.body}</p>
            <p className="mt-3 text-[0.9375rem]">
              Please read our{" "}
              <Link href="/refund-policy" className="font-medium text-wine-600 underline underline-offset-4">
                Refund &amp; Cancellation Policy
              </Link>{" "}
              and{" "}
              <Link href="/terms-and-conditions" className="font-medium text-wine-600 underline underline-offset-4">
                Terms of Use
              </Link>{" "}
              before paying.
            </p>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card title="Billing details" titleId="billing-title">
            <dl className="flex flex-col gap-3 text-[0.9375rem]">
              <div>
                <dt className="text-sm text-ink-muted">Name</dt>
                <dd className="font-medium">{customer.name || "—"}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Email (your receipt is sent here)</dt>
                <dd className="font-medium break-all">{customer.email || "Not added"}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Mobile number</dt>
                <dd className="font-medium">{customer.phone ? maskPhoneNumber(customer.phone) : "—"}</dd>
              </div>
            </dl>
            <p className="mt-4 text-sm text-ink-muted">
              Wrong email address?{" "}
              <Link href="/dashboard/settings#email" className="font-medium text-wine-600 underline underline-offset-4">
                Change it in Account Settings
              </Link>{" "}
              before paying.
            </p>
          </Card>

          <Card title="Payment" titleId="payment-title">
            {quote.available && price ? (
              <>
                <PayButton packageCode={quote.package.code} label={`Pay ${formatAmount(price.total)} now`} requireConsent />
                <p className="mt-3 text-sm text-ink-muted">
                  Secure payment by Razorpay: cards, UPI, net banking and wallets. Your membership is activated once
                  Razorpay confirms the payment, and we email your receipt.
                </p>
              </>
            ) : (
              <>
                <Notice tone="info">{quote.blocked?.message}</Notice>
                <Link href={action?.href ?? "/contact"} className={`${primaryButton} mt-4 w-full`}>
                  {action?.label ?? "Contact us"}
                </Link>
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
