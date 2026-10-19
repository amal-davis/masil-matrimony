import Image from "next/image";

import { Container } from "@/components/ui/container";
import { ArrowRightIcon } from "@/components/ui/icons";

import monogram from "@/public/images/masil-matrimony-monogram.png";

/**
 * Where "Get Launch Updates" should go. NOT CONNECTED: there is no newsletter,
 * enquiry or contact endpoint or page yet (backend/apps/enquiries is a
 * placeholder), so the button is hidden rather than pretending to subscribe
 * anyone. Set this to a real destination, e.g. "/contact" or a launch-updates
 * form backed by POST /enquiries/, and the button appears.
 */
const LAUNCH_UPDATES_HREF: string | null = null;

/** Launch announcement shown while member registration is not yet open. */
export function LaunchAnnouncement() {
  return (
    <section
      id="get-started"
      aria-labelledby="get-started-title"
      className="relative isolate scroll-mt-20 overflow-hidden bg-wine-800"
    >
      {/* Soft glow behind the monogram; decorative only. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(60%_80%_at_85%_50%,rgba(210,165,74,0.14),transparent_70%)]"
      />
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gold/40" />

      <Container className="grid items-center gap-10 py-14 sm:py-20 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-16">
        <div>
          <p className="font-display text-2xl text-gold-soft italic sm:text-[1.75rem]">Member Registration Opens Soon</p>
          <h2 id="get-started-title" className="mt-3 text-4xl leading-[1.1] font-medium text-ivory sm:text-5xl">
            Your New Beginning Starts Here
          </h2>
          <p className="mt-5 max-w-[58ch] text-base leading-[1.7] text-pretty text-ivory/85 sm:text-lg">
            We&apos;re preparing a thoughtful matrimonial experience to help individuals and families take the next
            step towards meaningful connections. Stay tuned for updates from Massil Matrimony.
          </p>

          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
            {LAUNCH_UPDATES_HREF && (
              <a
                href={LAUNCH_UPDATES_HREF}
                className="group inline-flex h-13 items-center justify-center gap-2.5 rounded-md bg-gold px-8 text-base font-medium text-wine-900 transition-colors duration-200 hover:bg-gold-soft focus-visible:outline-gold"
              >
                Get Launch Updates
                <ArrowRightIcon className="size-5 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none" />
              </a>
            )}
            <p className="flex items-center gap-3 text-[0.9375rem] text-gold-soft">
              <span aria-hidden="true" className="h-px w-8 shrink-0 bg-gold" />
              Be among the first to know when registration becomes available.
            </p>
          </div>
        </div>

        {/* Monogram in a double gold ring, beside the text from lg; stacked below it, it would only add height. */}
        <div aria-hidden="true" className="hidden justify-end lg:flex">
          <div className="relative flex size-56 items-center justify-center rounded-full border border-gold/50 lg:size-72">
            <div className="absolute inset-2.5 rounded-full border border-gold/20" />
            <Image
              src={monogram}
              alt=""
              sizes="160px"
              className="h-24 w-auto drop-shadow-[0_18px_28px_rgba(0,0,0,0.45)] lg:h-32"
            />
          </div>
        </div>
      </Container>
    </section>
  );
}
