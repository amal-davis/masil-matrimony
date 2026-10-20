import { Container } from "@/components/ui/container";
import { officeAddress } from "@/lib/site";

import { mapsEmbedUrl, mapsSearchUrl } from "../maps";

/**
 * Embedded Google Map of the office. Renders nothing until the real address is
 * set in lib/site.ts, so the page never shows an unrelated location.
 */
export function OfficeMap() {
  if (!officeAddress) return null;

  return (
    <section aria-labelledby="office-map-title" className="bg-white py-14 sm:py-20">
      <Container>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="office-map-title" className="text-3xl font-semibold sm:text-4xl">
              Find Our Office
            </h2>
            <p className="mt-3 text-lg text-pretty text-ink-muted">View our office location on the map.</p>
          </div>
          <a
            href={mapsSearchUrl(officeAddress)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-12 shrink-0 items-center justify-center rounded-md border border-wine-600 px-6 text-[0.9375rem] font-medium text-wine-600 transition-colors duration-200 hover:bg-brand-50 focus-visible:outline-wine-600"
          >
            Open in Google Maps<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </div>

        <div className="mt-8 aspect-[4/3] overflow-hidden rounded-xl border border-line bg-mist sm:aspect-video">
          <iframe
            title={`Map showing the Massil Matrimony office: ${officeAddress.join(", ")}`}
            src={mapsEmbedUrl(officeAddress)}
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            className="size-full border-0"
          />
        </div>
      </Container>
    </section>
  );
}
