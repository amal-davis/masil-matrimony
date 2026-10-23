import { A, P, Pending, SupportContacts, type LegalSection } from "./components/legal-document";
import { SERVICE_NAME } from "./config";

/**
 * The Shipping & Delivery Policy, from the owner's initial draft. It promises
 * no activation times or home-visit timelines: those are <Pending> decisions
 * (features/legal/config.ts). Needs legal review before publication.
 */
export const shippingSections: LegalSection[] = [
  {
    id: "nature-of-services",
    title: "Nature of our services",
    body: (
      <P>
        {SERVICE_NAME} mainly provides digital matrimonial membership and matchmaking services. Nothing is physically
        shipped for online membership packages, unless a specific physical product or document is expressly offered.
      </P>
    ),
  },
  {
    id: "online-memberships",
    title: "Delivery of online memberships",
    body: (
      <>
        <P>
          Once our payment provider and our systems have confirmed a successful payment, the membership you bought is
          activated in your account, according to the package you chose and our activation process.
        </P>
        <P>
          <Pending id="onlinePayments" />
        </P>
        <P>
          <Pending id="activation" />
        </P>
      </>
    ),
  },
  {
    id: "confirmation",
    title: "Confirmation and access",
    body: (
      <P>
        Your membership status and the benefits available to you are shown in your{" "}
        <A href="/dashboard/membership">member dashboard</A>. A payment confirmation or receipt is provided through the
        channels supported by our platform and payment provider.
      </P>
    ),
  },
  {
    id: "activation-delays",
    title: "Activation delays",
    body: (
      <P>
        If your payment was successful but your membership has not been updated, contact support with the transaction
        reference and your registered Matrimony ID. Our support team will look into the transaction and resolve the
        issue.
      </P>
    ),
  },
  {
    id: "assisted-services",
    title: "Assisted matchmaking services",
    body: (
      <>
        <P>
          For packages that include personal matchmaking assistance or home visits, such as Platinum and Royal, when the
          service starts, how appointments are scheduled, what the service covers and how it is delivered follow the
          agreed package terms and a schedule confirmed with you. Home visits are arranged by mutual agreement; they are
          not automatic or immediately available on purchase.
        </P>
        <P>
          <Pending id="assistedScope" />
        </P>
      </>
    ),
  },
  {
    id: "timelines",
    title: "Delivery timelines",
    body: (
      <>
        <P>
          Online access is provided after the payment has been verified and any required account or service activation
          steps have been completed. Any package-specific onboarding or appointment timeline will be shared before you
          buy.
        </P>
        <P>
          <Pending id="assistedTimeline" />
        </P>
      </>
    ),
  },
  {
    id: "support",
    title: "Contact and support",
    body: (
      <>
        <P>
          For help with membership access, activation or service delivery, contact {SERVICE_NAME} using our official
          support details:
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
