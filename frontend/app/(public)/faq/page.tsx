import type { Metadata } from "next";

import { Container } from "@/components/ui/container";
import { FaqAccordion } from "@/features/faq/components/faq-accordion";
import { faqs } from "@/features/faq/faqs";

export const metadata: Metadata = {
  title: "Frequently asked questions",
  description:
    "Answers about creating your profile, finding matches, privacy and getting started with Massil Matrimony.",
};

export default function FaqPage() {
  return (
    <Container className="max-w-4xl py-12 sm:py-16 lg:py-20">
      <p className="text-sm font-medium tracking-[0.12em] text-wine-600 uppercase">Massil Matrimony Help Center</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl lg:text-5xl">Frequently Asked Questions</h1>
      <p className="mt-4 max-w-2xl text-lg leading-relaxed text-pretty text-ink-muted">
        Everything you need to know about creating your profile, discovering meaningful matches, and getting
        started with Massil Matrimony.
      </p>

      <FaqAccordion items={faqs} headingLevel="h2" className="mt-10 sm:mt-12" />
    </Container>
  );
}
