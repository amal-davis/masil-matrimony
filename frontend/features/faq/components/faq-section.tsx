import Link from "next/link";

import { Container } from "@/components/ui/container";
import { ArrowRightIcon } from "@/components/ui/icons";

import { faqs, HOMEPAGE_FAQ_COUNT } from "../faqs";
import { FAQ_PATH } from "../paths";
import { FaqAccordion } from "./faq-accordion";

/**
 * Homepage FAQ: heading, introduction and a link to /faq on the left (above on
 * smaller screens), the first few questions on the right.
 */
export function FaqSection() {
  const items = faqs.slice(0, HOMEPAGE_FAQ_COUNT);

  return (
    <section id="faq" aria-labelledby="faq-title" className="scroll-mt-20 bg-white py-14 sm:py-20">
      <Container className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <p className="text-sm font-medium tracking-[0.12em] text-wine-600 uppercase">
            Massil Matrimony Help Center
          </p>
          <h2 id="faq-title" className="mt-3 text-3xl font-semibold sm:text-4xl">
            Frequently Asked Questions
          </h2>
          <p className="mt-4 max-w-xl text-lg leading-relaxed text-pretty text-ink-muted">
            Everything you need to know about creating your profile, discovering meaningful matches, and
            getting started with Massil Matrimony.
          </p>
          <Link
            href={FAQ_PATH}
            className="group mt-6 inline-flex h-12 items-center gap-2 rounded-md border border-wine-600 px-6 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-wine-600 hover:text-white focus-visible:outline-wine-600"
          >
            See all FAQs
            <ArrowRightIcon className="size-5 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
          </Link>
        </div>

        <FaqAccordion items={items} defaultOpen={[items[0].id]} />
      </Container>
    </section>
  );
}
