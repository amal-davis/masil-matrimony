import Image from "next/image";
import Link from "next/link";
import type { ComponentProps, ComponentType } from "react";

import { Container } from "@/components/ui/container";
import { FacebookIcon, InstagramIcon, MapPinIcon, WhatsAppIcon, YouTubeIcon } from "@/components/ui/icons";
import { footerLinks, legalLinks, officeAddress, socialLinks, type SocialPlatform } from "@/lib/site";

import logo from "@/public/images/masil-matrimony-logo.png";

import { CurrentYear } from "./current-year";

const BRAND = "Massil Matrimony";

const socialMeta: Record<SocialPlatform, { label: string; Icon: ComponentType<ComponentProps<"svg">> }> = {
  instagram: { label: "Instagram", Icon: InstagramIcon },
  facebook: { label: "Facebook", Icon: FacebookIcon },
  youtube: { label: "YouTube", Icon: YouTubeIcon },
  whatsapp: { label: "WhatsApp", Icon: WhatsAppIcon },
};

const linkClasses =
  "inline-flex min-h-11 items-center rounded-sm text-[0.9375rem] text-ivory/75 transition-colors duration-200 hover:text-gold-soft focus-visible:outline-gold lg:min-h-9";

/** Column heading with a short gold rule beneath it. */
function FooterHeading({ id, children }: { id: string; children: string }) {
  return (
    <h2 id={id} className="font-sans text-base font-semibold text-white">
      {children}
      <span aria-hidden="true" className="mt-3 block h-px w-8 bg-gold" />
    </h2>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto bg-wine-900 text-ivory">
      <div aria-hidden="true" className="h-px bg-gold/35" />

      <Container className="grid gap-12 py-14 sm:py-16 md:grid-cols-2 md:gap-x-12 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)] lg:gap-x-16 lg:py-20">
        {/* Brand and office */}
        <div className="md:col-span-2 lg:col-span-1">
          <Link href="/" className="inline-block rounded-sm focus-visible:outline-gold">
            {/* The artwork has transparent space above and below the mark; the negative margins absorb it. */}
            <Image src={logo} alt={`${BRAND} home`} sizes="176px" className="-my-[10%] h-auto w-36 sm:w-44" />
          </Link>
          <p className="mt-5 max-w-sm text-[0.9375rem] leading-relaxed text-pretty text-ivory/75">
            {BRAND} brings individuals and families together in the search for meaningful connections and lasting
            companionship.
          </p>

          <div className="mt-8 flex gap-3.5">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-gold/35 text-gold">
              <MapPinIcon className="size-5" />
            </span>
            <div className="min-w-0">
              <p className="font-semibold text-white">Our Office</p>
              {officeAddress ? (
                <>
                  <address className="mt-1 text-[0.9375rem] leading-relaxed break-words text-ivory/75 not-italic">
                    {officeAddress.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </address>
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(officeAddress.join(", "))}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex min-h-11 items-center rounded-sm text-[0.9375rem] font-medium text-gold-soft underline-offset-4 hover:underline focus-visible:outline-gold"
                  >
                    View on map<span className="sr-only"> (opens in a new tab)</span>
                  </a>
                </>
              ) : (
                <p className="mt-1 text-[0.9375rem] text-ivory/75">Our office address will be published here soon.</p>
              )}
            </div>
          </div>
        </div>

        {/* Quick links */}
        <nav aria-labelledby="footer-links-title">
          <FooterHeading id="footer-links-title">Quick Links</FooterHeading>
          <ul className="mt-4 flex flex-col">
            {footerLinks.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className={linkClasses}>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Social */}
        <div>
          <FooterHeading id="footer-social-title">Follow Us</FooterHeading>
          {socialLinks.length > 0 && (
            <ul aria-labelledby="footer-social-title" className="mt-5 flex flex-wrap gap-3">
              {socialLinks.map(({ platform, url }) => {
                const { label, Icon } = socialMeta[platform];
                return (
                  <li key={platform}>
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`${BRAND} on ${label} (opens in a new tab)`}
                        className="flex size-12 items-center justify-center rounded-full border border-gold/35 text-gold-soft transition-colors duration-200 hover:border-gold hover:bg-gold hover:text-wine-900 focus-visible:outline-gold"
                      >
                        <Icon className="size-5" />
                      </a>
                    ) : (
                      // No official account yet: show the icon, but don't pretend it goes anywhere.
                      <span
                        title={`${label}: coming soon`}
                        className="flex size-12 cursor-default items-center justify-center rounded-full border border-gold/25 text-gold-soft/60"
                      >
                        <Icon aria-hidden="true" className="size-5" />
                        <span className="sr-only">{label} (coming soon)</span>
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {socialLinks.some((link) => !link.url) && (
            <p className="mt-4 text-[0.9375rem] text-ivory/75">Our official channels are coming soon.</p>
          )}
          <p className="mt-5 text-[0.9375rem] text-ivory/75">Stay connected with {BRAND}.</p>
        </div>
      </Container>

      <div className="border-t border-ivory/10">
        <Container className="flex flex-col gap-3 py-6 text-sm text-ivory/65 sm:flex-row sm:items-center sm:justify-between">
          <p>
            &copy; <CurrentYear /> {BRAND}. All rights reserved.
          </p>
          {legalLinks.length > 0 && (
            <nav aria-label="Legal">
              <ul className="flex flex-wrap gap-x-6 gap-y-1">
                {legalLinks.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="inline-flex min-h-11 items-center rounded-sm transition-colors hover:text-gold-soft focus-visible:outline-gold lg:min-h-0"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </Container>
      </div>
    </footer>
  );
}
