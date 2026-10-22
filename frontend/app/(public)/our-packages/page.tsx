import type { Metadata } from "next";

import { Container } from "@/components/ui/container";
import { InfoIcon } from "@/components/ui/icons";
import { MembershipInformation } from "@/features/packages/components/membership-information";
import { PackageCard } from "@/features/packages/components/package-card";
import { membershipPackages } from "@/features/packages/packages";

export const metadata: Metadata = {
  title: "Membership Packages",
  description:
    "Compare Massil Matrimony's Diamond online membership, Platinum assisted matchmaking and Royal at-home matchmaking packages, with prices, GST, validity and included benefits.",
};

export default function OurPackagesPage() {
  return (
    <>
      <section aria-labelledby="packages-title" className="relative isolate overflow-hidden bg-wine-800">
        {/* Soft glow behind the heading; decorative only. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[radial-gradient(60%_90%_at_50%_0%,rgba(210,165,74,0.14),transparent_70%)]"
        />
        <Container className="max-w-3xl py-12 text-center sm:py-16 lg:py-20">
          <p className="text-sm font-medium tracking-[0.12em] text-gold uppercase">Membership options</p>
          <h1
            id="packages-title"
            className="mt-4 text-[2.25rem] leading-[1.1] font-medium text-ivory sm:text-5xl xl:text-[3.5rem]"
          >
            Choose Your Matchmaking Journey
          </h1>
          <div aria-hidden="true" className="mx-auto mt-6 flex w-fit items-center gap-3">
            <span className="h-px w-10 bg-gold/60" />
            <span className="size-1.5 rotate-45 bg-gold" />
            <span className="h-px w-10 bg-gold/60" />
          </div>
          <p className="mx-auto mt-6 max-w-[60ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            Whether you prefer to explore profiles independently or receive personalised matchmaking assistance,
            discover the membership option that best suits your preferences.
          </p>
          <p className="mt-4 text-[0.9375rem] font-medium text-gold-soft sm:text-base">
            Clear pricing. Defined benefits. A thoughtful approach to matchmaking.
          </p>
        </Container>
      </section>

      <section aria-labelledby="packages-list-title" className="bg-mist py-12 sm:py-16 lg:py-20">
        {/* Wide container: three text-heavy cards need the room to stay a reasonable height. */}
        <Container size="wide">
          <h2 id="packages-list-title" className="sr-only">
            Membership packages
          </h2>

          {/* No checkout exists yet: say so plainly before anyone picks a package. */}
          <div className="mx-auto mb-8 flex max-w-3xl gap-3.5 rounded-lg border border-line bg-white px-5 py-4 sm:mb-10">
            <InfoIcon className="mt-0.5 size-5 shrink-0 text-wine-600" />
            <p className="text-[0.9375rem] leading-relaxed text-pretty text-ink sm:text-base">
              Memberships can&apos;t be bought online yet. Each package button opens our contact form, where you can
              send an enquiry. Our team will confirm availability, the applicable terms and how activation works.
              Choosing a package here doesn&apos;t activate a membership.
            </p>
          </div>

          {/* One column on phones, two on tablets (Royal spans the second row), three from lg. */}
          <ul className="flex flex-col gap-6 md:grid md:grid-cols-2 md:gap-x-6 md:gap-y-0 lg:grid-cols-3">
            {membershipPackages.map((pkg) => (
              <PackageCard key={pkg.id} pkg={pkg} />
            ))}
          </ul>
        </Container>
      </section>

      <MembershipInformation />
    </>
  );
}
