import type { Metadata } from "next";

import { AboutCta } from "@/features/about/components/about-cta";
import { AboutHero } from "@/features/about/components/about-hero";
import { CoreValues } from "@/features/about/components/core-values";
import { MatchmakingApproach } from "@/features/about/components/matchmaking-approach";
import { MissionVision } from "@/features/about/components/mission-vision";
import { WhoWeAre } from "@/features/about/components/who-we-are";

export const metadata: Metadata = {
  title: "About Us",
  description:
    "Learn about Massil Matrimony: our mission, vision and values, and our thoughtful approach to helping individuals and families find meaningful matrimonial connections.",
};

export default function AboutUsPage() {
  return (
    <>
      <AboutHero />
      <WhoWeAre />
      <MissionVision />
      <CoreValues />
      <MatchmakingApproach />
      <AboutCta />
    </>
  );
}
