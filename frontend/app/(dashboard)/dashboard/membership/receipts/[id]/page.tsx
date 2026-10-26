import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { secondaryButton } from "@/features/dashboard/components/ui";
import { formatDate } from "@/features/dashboard/format";
import { getReceipt } from "@/features/dashboard/server-api";
import { PrintButton } from "@/features/payments/components/print-button";
import { formatAmount, formatRate } from "@/features/payments/format";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Payment Receipt", robots: { index: false, follow: false } };

/**
 * Not an instant navigation, by design: the URL segment is only known per request
 * (the dashboard shell reads it with usePathname for its navigation), and the page
 * waits for this member's own data from the API before it can show anything.
 */
export const instant = false;

/**
 * A payment receipt, printable (the dashboard's navigation is hidden when
 * printing). Only the receipt's owner can load it: the API checks. Seller
 * details appear only as configured on the server; nothing is filled in here.
 */
export default async function ReceiptPage({ params }: PageProps<"/dashboard/membership/receipts/[id]">) {
  const { id } = await params;
  const receipt = await getReceipt(id);
  if (!receipt) notFound();
  const { seller, customer, item, amounts, payment } = receipt;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href={`/dashboard/membership/purchases/${payment.purchase_reference}`} className={secondaryButton}>
          Back to purchase
        </Link>
        <PrintButton />
      </div>

      <article
        aria-labelledby="receipt-title"
        className="mx-auto max-w-3xl rounded-xl border border-line bg-white p-6 sm:p-10 print:max-w-none print:border-0 print:p-0"
      >
        {payment.test_mode && (
          <p className="mb-6 rounded-md border border-accent-400 bg-accent-100 px-4 py-2 text-sm font-medium">
            Test mode: no real money was charged.
          </p>
        )}
        <header className="flex flex-col gap-4 border-b border-line pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-display text-2xl font-semibold text-wine-600">{seller.brand}</p>
            {seller.legal_name && <p className="mt-1 text-sm font-medium">{seller.legal_name}</p>}
            {seller.address && <p className="text-sm whitespace-pre-line text-ink-muted">{seller.address}</p>}
            {seller.gstin && <p className="text-sm text-ink-muted">GSTIN: {seller.gstin}</p>}
          </div>
          <div className="sm:text-right">
            <h1 id="receipt-title" className="text-xl font-semibold">{receipt.title}</h1>
            <p className="mt-1 text-sm">No. {receipt.number}</p>
            <p className="text-sm text-ink-muted">Date: {formatDate(receipt.issued_at)}</p>
          </div>
        </header>

        <section aria-label="Billed to" className="border-b border-line py-5 text-[0.9375rem]">
          <p className="text-sm text-ink-muted">Billed to</p>
          <p className="font-medium">{customer.name || "Member"}</p>
          <p className="text-ink-muted">{customer.email}</p>
        </section>

        <table className="mt-5 w-full text-left text-[0.9375rem]">
          <caption className="sr-only">Amounts</caption>
          <thead>
            <tr className="border-b border-line text-sm text-ink-muted">
              <th scope="col" className="pb-2 font-medium">Description</th>
              <th scope="col" className="pb-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line">
              <td className="py-3">
                <span className="font-medium">{item.package}</span>
                <span className="block text-sm text-ink-muted">
                  {item.starts_at
                    ? `Valid ${formatDate(item.starts_at)} – ${formatDate(item.ends_at)} (${item.validity_months} months)`
                    : item.description}
                </span>
              </td>
              <td className="py-3 text-right tabular-nums">{formatAmount(amounts.base)}</td>
            </tr>
            <tr className="border-b border-line">
              <td className="py-3">GST ({formatRate(amounts.gst_rate)})</td>
              <td className="py-3 text-right tabular-nums">{formatAmount(amounts.gst)}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="pt-4 text-lg font-semibold">Total paid ({amounts.currency})</th>
              <td className="pt-4 text-right text-lg font-semibold tabular-nums">{formatAmount(amounts.total)}</td>
            </tr>
          </tfoot>
        </table>

        <dl className="mt-8 grid gap-3 rounded-lg bg-mist p-4 text-sm sm:grid-cols-2 print:bg-transparent print:p-0">
          <div>
            <dt className="text-ink-muted">Paid on</dt>
            <dd className="font-medium">{formatDate(payment.paid_at)}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Purchase reference</dt>
            <dd className="font-medium break-all">{payment.purchase_reference}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Razorpay payment ID</dt>
            <dd className="font-medium break-all">{payment.razorpay_payment_id}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Razorpay order ID</dt>
            <dd className="font-medium break-all">{payment.razorpay_order_id}</dd>
          </div>
        </dl>

        <footer className={cn("mt-8 border-t border-line pt-5 text-sm text-ink-muted")}>
          <p>This is a payment receipt for your membership purchase.</p>
          {(seller.email || seller.phone) && (
            <p className="mt-1">
              Questions about this payment: {[seller.email, seller.phone].filter(Boolean).join(" · ")}
            </p>
          )}
        </footer>
      </article>
    </>
  );
}
