import { A, List, P, Pending, SupportContacts, type LegalSection } from "./components/legal-document";
import { PackageFeeList } from "./components/package-fee-list";
import { SERVICE_NAME } from "./config";

/**
 * The Refund & Cancellation Policy, from the owner's initial draft. It sets no
 * refund rules, deductions or timelines of its own: those are <Pending>
 * decisions (features/legal/config.ts). Package details come from
 * features/packages/packages.ts. Needs legal review before publication.
 */
export const refundSections: LegalSection[] = [
  {
    id: "overview",
    title: "Overview",
    body: (
      <P>
        {SERVICE_NAME} provides online matrimonial membership and matchmaking services. This policy explains how payment
        issues, cancellation requests and refund requests are handled. It forms part of our{" "}
        <A href="/terms-and-conditions">Terms &amp; Conditions</A>.
      </P>
    ),
  },
  {
    id: "cancellation",
    title: "Cancelling a membership",
    body: (
      <P>
        If you wish to cancel a membership or an assisted matchmaking service, contact our official support team using
        the contact details published on our website (see &ldquo;How to request a refund&rdquo; below). Submitting a
        cancellation request does not by itself mean that a refund is approved.
      </P>
    ),
  },
  {
    id: "eligibility",
    title: "Refund eligibility",
    body: (
      <>
        <P>Whether a refund is due depends on:</P>
        <List
          items={[
            "the membership or service purchased;",
            "the terms that applied to it when it was bought;",
            "how much of the service has already been delivered; and",
            "applicable law.",
          ]}
        />
        <P>Every request is assessed fairly under the published terms.</P>
        <P>This policy covers our current packages:</P>
        <PackageFeeList />
        <P>
          <Pending id="refunds" />
        </P>
      </>
    ),
  },
  {
    id: "payment-problems",
    title: "Failed, duplicate or unsuccessful payments",
    body: (
      <>
        <P>
          If money was debited but your membership was not activated, or you were charged twice for the same purchase,
          contact support with the transaction reference and the payment date. We will check the payment status with
          our payment provider and take appropriate steps to resolve the issue.
        </P>
        <P>
          <Pending id="onlinePayments" />
        </P>
      </>
    ),
  },
  {
    id: "approved-refunds",
    title: "Approved refunds",
    body: (
      <>
        <P>
          When a refund is approved, it is initiated through the payment provider, or to the payment method used for the
          original transaction, where that is supported. How long it then takes to reach your account depends on the
          payment provider, your bank and the payment method.
        </P>
        <P>
          <Pending id="refundTimeline" />
        </P>
      </>
    ),
  },
  {
    id: "how-to-request",
    title: "How to request a refund",
    body: (
      <>
        <P>
          Contact our official support channel (see &ldquo;Complaints and disputes&rdquo; for the contact details) and
          include:
        </P>
        <List
          items={[
            "your registered email address or Matrimony ID;",
            "the transaction reference;",
            "the payment date and amount; and",
            "the reason for your request.",
          ]}
        />
        <P>
          <strong className="font-semibold">
            We will never ask for your password, one-time codes (OTPs) or full card details.
          </strong>{" "}
          Do not share them with anyone who contacts you claiming to be from {SERVICE_NAME}.
        </P>
      </>
    ),
  },
  {
    id: "complaints",
    title: "Complaints and disputes",
    body: (
      <>
        <P>
          If a payment issue is not resolved, contact our official support or grievance contact. Your statutory consumer
          rights, and the protections offered by your bank or payment system, are not affected by this policy.
        </P>
        <SupportContacts />
        <P>
          You can also reach us through our <A href="/contact">Contact page</A>.
        </P>
      </>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <P>
        Changes to this policy will be published on this page, with an updated date shown at the top.
      </P>
    ),
  },
];
