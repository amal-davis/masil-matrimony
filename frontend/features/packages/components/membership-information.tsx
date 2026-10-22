import Link from "next/link";

import { Container } from "@/components/ui/container";
import { InfoIcon } from "@/components/ui/icons";
import { legalLinks } from "@/lib/site";

const points = [
  "Membership validity begins from the activation date.",
  "Benefits depend on the selected package and its terms.",
  "Contact details are shared only subject to applicable consent and privacy settings.",
  "Assisted matchmaking and at-home service arrangements are subject to the relevant service agreement.",
  "GST treatment is as stated for each package and subject to the applicable tax rules.",
  "Please review the published Terms & Conditions and Privacy Policy before choosing a membership.",
];

/** Terms that apply to every package, kept at body size so nothing material is hidden in a footnote. */
export function MembershipInformation() {
  return (
    <section aria-labelledby="membership-info-title" className="bg-white py-14 sm:py-20">
      <Container className="max-w-3xl">
        <h2 id="membership-info-title" className="text-3xl font-semibold sm:text-4xl">
          Important Membership Information
        </h2>

        <ul className="mt-8 flex flex-col divide-y divide-line border-y border-line">
          {points.map((point) => (
            <li key={point} className="flex gap-3.5 py-4">
              <InfoIcon className="mt-0.5 size-5 shrink-0 text-wine-600" />
              <p className="text-base leading-relaxed text-pretty text-ink">{point}</p>
            </li>
          ))}
        </ul>

        {legalLinks.length > 0 ? (
          <nav aria-label="Membership policies" className="mt-6">
            <ul className="flex flex-wrap gap-x-6 gap-y-2">
              {legalLinks.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="inline-flex min-h-11 items-center rounded-sm text-base font-medium text-wine-600 underline underline-offset-4 hover:text-wine-800 focus-visible:outline-wine-600"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : (
          <p className="mt-6 text-base leading-relaxed text-ink-muted">
            Our Terms &amp; Conditions and Privacy Policy are not yet published on this website. They will be linked
            here once available.
          </p>
        )}

        <p className="mt-4 text-base leading-relaxed text-ink-muted">
          Questions about a package?{" "}
          <Link
            href="/contact"
            className="rounded-sm font-medium text-wine-600 underline underline-offset-4 hover:text-wine-800 focus-visible:outline-wine-600"
          >
            Contact us
          </Link>{" "}
          and our team will explain what each membership includes.
        </p>
      </Container>
    </section>
  );
}
