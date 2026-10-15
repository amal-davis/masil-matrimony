import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { HeroSlider } from "@/features/home-hero/components/hero-slider";
import { HERO_SLIDE_DURATION_MS, heroSlides } from "@/features/home-hero/slides";
import {
  HighlightedProfiles,
  HighlightedProfilesSkeleton,
} from "@/features/highlighted-profiles/components/highlighted-profiles";
import { PartnerSearchFilter } from "@/features/partner-search/components/partner-search-filter";
import { QuickRegistrationForm } from "@/features/registration/components/quick-registration-form";
import { config } from "@/lib/config";

const steps = [
  {
    title: "Create your profile",
    body: "Share details about yourself, your family and the partner you are looking for.",
  },
  {
    title: "Get verified",
    body: "Our team reviews every profile so you can connect with confidence.",
  },
  {
    title: "Connect with matches",
    body: "Browse compatible profiles, express interest and take the next step together.",
  },
];

const values = [
  {
    title: "Verified profiles",
    body: "Each profile is screened by our verification team before it becomes visible to members.",
  },
  {
    title: "Privacy you control",
    body: "Decide who can see your photos and contact details. Nothing private is public by default.",
  },
  {
    title: "Personal assistance",
    body: "Our relationship advisors can help you and your family through every stage of the search.",
  },
];

export default function HomePage() {
  return (
    <>
      <HeroSlider
        slides={heroSlides}
        durationMs={HERO_SLIDE_DURATION_MS}
        title={`${config.siteName}: trusted matrimonial service for Kerala families`}
        aside={<QuickRegistrationForm />}
      />

      <section aria-label="Partner search" className="bg-surface-muted py-10 sm:py-14">
        <Container>
          <PartnerSearchFilter
            title="Search Your Partner"
            description="Discover compatible profiles based on your preferences."
          />
        </Container>
      </section>

      <Suspense fallback={<HighlightedProfilesSkeleton />}>
        <HighlightedProfiles />
      </Suspense>

      <section id="how-it-works" className="scroll-mt-20 py-20">
        <Container>
          <h2 className="text-center text-3xl font-semibold sm:text-4xl">How it works</h2>
          <ol className="mt-12 grid gap-6 md:grid-cols-3">
            {steps.map((step, index) => (
              <li key={step.title} className="rounded-2xl border border-line bg-white p-6">
                <span className="font-display text-3xl text-accent-600">{index + 1}</span>
                <h3 className="mt-3 text-xl font-semibold">{step.title}</h3>
                <p className="mt-2 text-ink-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </Container>
      </section>

      <section id="why-us" className="scroll-mt-20 bg-surface-muted py-20">
        <Container>
          <h2 className="text-center text-3xl font-semibold sm:text-4xl">Why families choose us</h2>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {values.map((value) => (
              <div key={value.title} className="rounded-2xl bg-white p-6 shadow-sm">
                <h3 className="text-xl font-semibold text-brand-800">{value.title}</h3>
                <p className="mt-2 text-ink-muted">{value.body}</p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      <section id="get-started" className="scroll-mt-20 py-20">
        <Container className="max-w-3xl text-center">
          <h2 className="text-3xl font-semibold sm:text-4xl">Member registration opens soon</h2>
          <p className="mt-4 text-lg text-ink-muted">
            We are preparing a secure registration and verification process. Please check back shortly.
          </p>
        </Container>
      </section>
    </>
  );
}
