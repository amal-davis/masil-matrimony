import type { Metadata } from "next";
import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { MembershipInformation } from "@/features/packages/components/membership-information";
import { PackageCatalogue, PackageCatalogueFallback } from "@/features/packages/components/package-catalogue";

export const metadata: Metadata = {
  title: "Membership Packages",
  description:
    "Compare Massil Matrimony's Free, Silver, Gold and Diamond online memberships with Platinum assisted matchmaking and Royal at-home matchmaking: prices, GST, validity, contact access and included benefits.",
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
            className="mt-4 text-[2.25rem] leading-[1.1] font-medium text-balance text-ivory sm:text-5xl xl:text-[3.5rem]"
          >
            Choose Your Matchmaking Journey
          </h1>
          <div aria-hidden="true" className="mx-auto mt-6 flex w-fit items-center gap-3">
            <span className="h-px w-10 bg-gold/60" />
            <span className="size-1.5 rotate-45 bg-gold" />
            <span className="h-px w-10 bg-gold/60" />
          </div>
          <p className="mx-auto mt-6 max-w-[60ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            Start with a free profile and search on your own, add a paid online membership for more ways to connect,
            or let a dedicated Massil matchmaker guide your family&apos;s search.
          </p>
          <p className="mt-4 text-[0.9375rem] font-medium text-gold-soft sm:text-base">
            Clear pricing. Defined benefits. A thoughtful approach to matchmaking.
          </p>
        </Container>
      </section>

      {/* Prices come from the API at request time, so an admin change shows at once. */}
      <Suspense fallback={<PackageCatalogueFallback />}>
        <PackageCatalogue />
      </Suspense>

      <MembershipInformation />
    </>
  );
}
