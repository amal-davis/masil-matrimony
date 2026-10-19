import { Suspense } from "react";

import { Container } from "@/components/ui/container";
import { BrandBanner } from "@/features/brand-banner/components/brand-banner";
import { FaqSection } from "@/features/faq/components/faq-section";
import { HeroSlider } from "@/features/home-hero/components/hero-slider";
import { HERO_SLIDE_DURATION_MS, heroSlides } from "@/features/home-hero/slides";
import { HowItWorks } from "@/features/home-info/components/how-it-works";
import { LaunchAnnouncement } from "@/features/home-info/components/launch-announcement";
import { WhyChooseUs } from "@/features/home-info/components/why-choose-us";
import {
  HighlightedProfiles,
  HighlightedProfilesSkeleton,
} from "@/features/highlighted-profiles/components/highlighted-profiles";
import { PartnerSearchFilter } from "@/features/partner-search/components/partner-search-filter";
import { QuickRegistrationForm } from "@/features/registration/components/quick-registration-form";
import {
  SuccessStories,
  SuccessStoriesSkeleton,
} from "@/features/success-stories/components/success-stories";
import { config } from "@/lib/config";

export default function HomePage() {
  return (
    <>
      <HeroSlider
        slides={heroSlides}
        durationMs={HERO_SLIDE_DURATION_MS}
        title={`${config.siteName}: trusted matrimonial service for Kerala families`}
        aside={
          // Target of in-page "register" links (e.g. the brand banner's call to action).
          <div id="register" className="scroll-mt-24">
            <QuickRegistrationForm />
          </div>
        }
      />

      <section aria-label="Partner search" className="bg-surface-muted py-12 sm:py-16">
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

      <Suspense fallback={<SuccessStoriesSkeleton />}>
        <SuccessStories />
      </Suspense>

      <FaqSection />

      <BrandBanner />

      <HowItWorks />

      <WhyChooseUs />

      <LaunchAnnouncement />
    </>
  );
}
