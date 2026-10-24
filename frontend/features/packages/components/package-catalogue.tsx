import Link from "next/link";

import { Container } from "@/components/ui/container";
import { InfoIcon, LockIcon, PhoneIcon } from "@/components/ui/icons";

import { getPackages } from "../api";
import { formatInr, type MembershipPackage } from "../packages";
import { PackageCard } from "./package-card";

const listFormat = new Intl.ListFormat("en-IN", { style: "long", type: "conjunction" });
const names = (items: MembershipPackage[]) => listFormat.format(items.map((item) => item.name));

function PackageGroup({
  id,
  title,
  intro,
  packages,
  columns,
}: {
  id: string;
  title: string;
  intro: string;
  packages: MembershipPackage[];
  columns: string;
}) {
  if (packages.length === 0) return null;
  return (
    <section aria-labelledby={id}>
      <div className="max-w-3xl">
        <h2 id={id} className="text-3xl font-semibold text-balance sm:text-4xl">
          {title}
        </h2>
        <p className="mt-3 text-base leading-relaxed text-pretty text-ink-muted sm:text-lg">{intro}</p>
      </div>
      {/* Cards stack on phones; from md each card is a subgrid, so the row gap separates card rows only. */}
      <ul className={`mt-8 flex flex-col gap-6 md:grid md:gap-x-6 md:gap-y-8 ${columns}`}>
        {packages.map((pkg) => (
          <PackageCard key={pkg.id} pkg={pkg} />
        ))}
      </ul>
    </section>
  );
}

/** How contact access and GST work, written from the package data so the numbers always match the cards. */
function HowItWorks({ packages }: { packages: MembershipPackage[] }) {
  const withContacts = packages.filter((item) => item.contactViewLimit !== null);
  const assisted = packages.filter((item) => item.category === "assisted");
  const free = packages.find((item) => item.id === "free");
  const gstExtra = packages.filter((item) => item.taxTreatment === "gst_extra");
  const gstStated = packages.filter((item) => item.taxTreatment === "gst_stated");

  const contactPoints = [
    free && `${free.name} doesn't include other members' mobile numbers.`,
    withContacts.length > 0 &&
      `Paid online memberships let you view other members' numbers, up to a limit of different members during the membership period: ${listFormat.format(
        withContacts.map((item) => `${item.contactViewLimit} with ${item.name}`),
      )}.`,
    "Viewing the same member's number again during your membership doesn't use another one. Unused views end when the membership does; they don't carry over to a renewal.",
    "A number is shown only if that member has chosen to share it with paid members. They can stop sharing at any time, and their number is then hidden again.",
    assisted.length > 0 &&
      `On ${names(assisted)}, your matchmaker coordinates the exchange of contact details, with both families' consent.`,
  ].filter((point): point is string => Boolean(point));

  const gstPoints = [
    gstExtra.length > 0 &&
      `Fees for ${names(gstExtra)} are shown before GST. Applicable GST is added to the fee when you pay.`,
    ...gstStated.map(
      (item) =>
        `${item.name}'s ${formatInr(item.price.amount)} includes GST at the stated rate of ${item.statedGstRate}%. The final tax amount depends on the GST rate applicable to the service.`,
    ),
    free && `${free.name} has no fee.`,
  ].filter((point): point is string => Boolean(point));

  return (
    <section aria-labelledby="how-it-works-title" className="bg-white py-14 sm:py-20">
      <Container size="wide">
        <h2 id="how-it-works-title" className="max-w-3xl text-3xl font-semibold text-balance sm:text-4xl">
          Contact numbers, privacy and GST
        </h2>
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-line p-6 sm:p-8">
            <h3 className="flex items-center gap-3 text-xl font-semibold">
              <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-full bg-brand-50 text-wine-600">
                <PhoneIcon className="size-5" />
              </span>
              How contact-number access works
            </h3>
            <ul className="mt-5 flex flex-col gap-3.5">
              {contactPoints.map((point) => (
                <li key={point} className="flex gap-3 text-base leading-relaxed text-pretty text-ink">
                  <span aria-hidden="true" className="mt-2.5 size-1.5 shrink-0 rotate-45 bg-wine-600" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col gap-6">
            <div className="rounded-xl border border-line p-6 sm:p-8">
              <h3 className="flex items-center gap-3 text-xl font-semibold">
                <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-full bg-brand-50 text-wine-600">
                  <LockIcon className="size-5" />
                </span>
                Your own number stays private
              </h3>
              <p className="mt-4 text-base leading-relaxed text-pretty text-ink">
                Your mobile number is never shown on your public profile. Paid members can see it only if you turn
                on contact sharing in your{" "}
                <Link
                  href="/dashboard/settings"
                  className="rounded-sm font-medium text-wine-600 underline underline-offset-4 hover:text-wine-800 focus-visible:outline-wine-600"
                >
                  privacy settings
                </Link>
                . It is off until you choose to share it.
              </p>
            </div>
            <div className="rounded-xl border border-line p-6 sm:p-8">
              <h3 className="flex items-center gap-3 text-xl font-semibold">
                <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-full bg-brand-50 text-wine-600">
                  <InfoIcon className="size-5" />
                </span>
                Fees and GST
              </h3>
              <ul className="mt-5 flex flex-col gap-3.5">
                {gstPoints.map((point) => (
                  <li key={point} className="flex gap-3 text-base leading-relaxed text-pretty text-ink">
                    <span aria-hidden="true" className="mt-2.5 size-1.5 shrink-0 rotate-45 bg-wine-600" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

/** The package list. Reads the API at request time, so render it inside <Suspense>. */
export async function PackageCatalogue() {
  const result = await getPackages();

  if (!result.ok || result.packages.length === 0) {
    return (
      <section aria-labelledby="packages-unavailable-title" className="bg-mist py-14 sm:py-20">
        <Container className="max-w-3xl">
          <div role="status" className="rounded-xl border border-line bg-white p-6 sm:p-8">
            <h2 id="packages-unavailable-title" className="text-2xl font-semibold">
              Package details are unavailable right now
            </h2>
            <p className="mt-3 text-base leading-relaxed text-ink">
              We couldn&apos;t load our current packages and prices. Please refresh the page in a moment, or{" "}
              <Link href="/contact" className="font-medium text-wine-600 underline underline-offset-4">
                contact us
              </Link>{" "}
              and our team will explain each membership.
            </p>
          </div>
        </Container>
      </section>
    );
  }

  const online = result.packages.filter((item) => item.category === "online");
  const assisted = result.packages.filter((item) => item.category === "assisted");

  return (
    <>
      <section aria-label="Membership packages" className="bg-mist py-12 sm:py-16 lg:py-20">
        <Container size="wide" className="flex flex-col gap-14 sm:gap-20">
          {/* No checkout exists yet: say so plainly before anyone picks a package. */}
          <div className="mx-auto flex max-w-3xl gap-3.5 rounded-lg border border-line bg-white px-5 py-4">
            <InfoIcon className="mt-0.5 size-5 shrink-0 text-wine-600" />
            <p className="text-[0.9375rem] leading-relaxed text-pretty text-ink sm:text-base">
              Paid memberships can&apos;t be bought online yet. Each paid package button opens our contact form, where
              you can send an enquiry. Our team will confirm the applicable terms and activate your membership once
              payment is confirmed. Choosing a package here doesn&apos;t activate a membership.
            </p>
          </div>

          <PackageGroup
            id="online-packages-title"
            title="Online memberships"
            intro="Search and connect with members yourself. Start free, or choose a paid membership for unlimited interests and access to member contact numbers."
            packages={online}
            // Four columns only where each card still has room for its benefit list.
            columns="md:grid-cols-2 xl:grid-cols-4"
          />

          <PackageGroup
            id="assisted-packages-title"
            title="Assisted matchmaking"
            intro="A dedicated Massil matchmaker searches, shortlists and coordinates on your family's behalf, under a signed service agreement."
            packages={assisted}
            columns="md:grid-cols-2"
          />
        </Container>
      </section>

      <HowItWorks packages={result.packages} />
    </>
  );
}

/** Shown while the packages load: the same outline, so the page doesn't jump. */
export function PackageCatalogueFallback() {
  return (
    <section aria-label="Loading membership packages" aria-busy="true" className="bg-mist py-12 sm:py-16 lg:py-20">
      <Container size="wide">
        <p className="sr-only">Loading membership packages…</p>
        <ul aria-hidden="true" className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <li key={index} className="h-[36rem] animate-pulse rounded-xl border border-line bg-white motion-reduce:animate-none" />
          ))}
        </ul>
      </Container>
    </section>
  );
}
