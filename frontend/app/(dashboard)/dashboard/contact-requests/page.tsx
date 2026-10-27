import type { Metadata } from "next";

import { ContactExchangeCard } from "@/features/dashboard/components/contact-exchange-card";
import { EmptyState, PageHeader } from "@/features/dashboard/components/ui";
import { getContactExchanges } from "@/features/dashboard/server-api";

export const metadata: Metadata = { title: "Contact Requests" };

/**
 * Exchanges of mobile numbers proposed by a Massil matchmaker that involve the
 * member. Each member decides for themselves; numbers appear only once both consent.
 */
export default async function ContactRequestsPage() {
  const exchanges = await getContactExchanges();
  return (
    <>
      <PageHeader
        title="Contact Requests"
        description="A Massil matchmaker asks both members before any mobile numbers are shared. You can decline, or withdraw your consent until both of you have agreed."
      />
      {exchanges.length === 0 ? (
        <EmptyState title="No contact requests">
          When a matchmaker proposes exchanging mobile numbers with another member, you&apos;ll be asked here.
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-4">
          {exchanges.map((exchange) => (
            <li key={exchange.id}>
              <ContactExchangeCard exchange={exchange} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
