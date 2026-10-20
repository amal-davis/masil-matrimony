import Image from "next/image";

import { Container } from "@/components/ui/container";

import photo from "@/public/images/hero/couple-lotus-field.jpg";

export function WhoWeAre() {
  return (
    <section aria-labelledby="who-we-are-title" className="bg-white py-14 sm:py-20">
      <Container className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-mist lg:aspect-[5/4]">
          <Image
            src={photo}
            alt="A smiling couple in traditional Kerala dress among lotus flowers"
            fill
            sizes="(min-width: 1024px) 34rem, 100vw"
            placeholder="blur"
            className="object-cover object-[62%_30%]"
          />
        </div>

        <div>
          <h2 id="who-we-are-title" className="text-3xl font-semibold sm:text-4xl">
            Who We Are
          </h2>
          <span aria-hidden="true" className="mt-4 block h-px w-12 bg-wine-600" />
          <div className="mt-6 max-w-[62ch] space-y-5 text-base leading-[1.75] text-pretty text-ink-muted sm:text-lg">
            <p>
              Massil Matrimony is being developed as a dedicated platform for individuals and families seeking
              meaningful matrimonial connections. Our aim is to make the process of discovering potential life
              partners clearer, more thoughtful, and easier to navigate.
            </p>
            <p>
              We recognise that choosing a life partner is an important personal and family decision. We want the
              Massil Matrimony experience to encourage thoughtful choices, mutual respect, and meaningful
              conversations.
            </p>
          </div>
        </div>
      </Container>
    </section>
  );
}
