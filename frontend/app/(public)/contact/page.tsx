import type { Metadata } from "next";

import { Container } from "@/components/ui/container";
import { ContactForm } from "@/features/contact/components/contact-form";
import { ContactInfo } from "@/features/contact/components/contact-info";
import { OfficeMap } from "@/features/contact/components/office-map";

export const metadata: Metadata = {
  title: "Contact Us",
  description:
    "Have a question about Massil Matrimony? Send us a message through our contact form and we'll help you find the right way forward.",
};

export default function ContactPage() {
  return (
    <>
      <section aria-labelledby="contact-title" className="relative isolate overflow-hidden bg-wine-800">
        {/* Soft glow behind the heading; decorative only. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[radial-gradient(60%_90%_at_50%_0%,rgba(210,165,74,0.14),transparent_70%)]"
        />
        <Container className="max-w-3xl py-12 text-center sm:py-16 lg:py-20">
          <p className="text-sm font-medium tracking-[0.12em] text-gold uppercase">We&apos;re here to help</p>
          <h1
            id="contact-title"
            className="mt-4 text-[2.25rem] leading-[1.1] font-medium text-ivory sm:text-5xl xl:text-[3.5rem]"
          >
            Contact Massil Matrimony
          </h1>
          <div aria-hidden="true" className="mx-auto mt-6 flex w-fit items-center gap-3">
            <span className="h-px w-10 bg-gold/60" />
            <span className="size-1.5 rotate-45 bg-gold" />
            <span className="h-px w-10 bg-gold/60" />
          </div>
          <p className="mx-auto mt-6 max-w-[56ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            Have a question or need more information? Send us a message, and we&apos;ll help you find the right way
            forward.
          </p>
        </Container>
      </section>

      <section aria-label="Contact details and form" className="bg-mist py-12 sm:py-16 lg:py-20">
        {/* Form first on phones, where it's the main way to reach us; details on the left from lg. */}
        <Container className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-8">
          <div className="order-2 lg:order-1">
            <ContactInfo />
          </div>
          <div className="order-1 lg:order-2">
            <ContactForm />
          </div>
        </Container>
      </section>

      <OfficeMap />
    </>
  );
}
