import type { ComponentProps, ComponentType, ReactNode } from "react";

import { MailIcon, MapPinIcon, PhoneIcon } from "@/components/ui/icons";
import { socialMeta } from "@/components/ui/social-meta";
import { contactEmail, contactPhone, officeAddress, socialLinks } from "@/lib/site";
import { cn } from "@/lib/utils";

import { mapsSearchUrl } from "../maps";

const BRAND = "Massil Matrimony";

const detailLink =
  "inline-flex min-h-11 items-center rounded-sm text-base font-medium break-all text-ivory underline-offset-4 transition-colors duration-200 hover:text-gold-soft hover:underline focus-visible:outline-gold sm:text-[1.0625rem]";

const pending = "mt-1 text-[0.9375rem] leading-relaxed text-ivory/70";

function DetailRow({
  title,
  Icon,
  children,
}: {
  title: string;
  Icon: ComponentType<ComponentProps<"svg">>;
  children: ReactNode;
}) {
  return (
    <li className="flex gap-4">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-full border border-gold/35 text-gold">
        <Icon className="size-[1.375rem]" />
      </span>
      <div className="min-w-0 pt-0.5">
        <h3 className="font-sans text-sm font-medium tracking-[0.04em] text-gold-soft">{title}</h3>
        {children}
      </div>
    </li>
  );
}

/**
 * Contact details on a wine panel. Every value comes from lib/site.ts; a
 * detail that isn't confirmed yet says so instead of showing a made-up value.
 */
export function ContactInfo() {
  const hasPendingSocial = socialLinks.some((link) => !link.url);

  return (
    <div className="relative isolate h-full overflow-hidden rounded-xl bg-wine-800 p-6 text-ivory sm:p-8">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(80%_60%_at_100%_0%,rgba(210,165,74,0.14),transparent_70%)]"
      />

      <h2 className="text-2xl font-semibold text-ivory sm:text-3xl">Get in Touch</h2>
      <span aria-hidden="true" className="mt-4 block h-px w-10 bg-gold" />

      <ul className="mt-7 flex flex-col gap-6">
        <DetailRow title="Email Us" Icon={MailIcon}>
          {contactEmail ? (
            <a href={`mailto:${contactEmail}`} className={detailLink}>
              {contactEmail}
            </a>
          ) : (
            <p className={pending}>Our email address will be published here soon.</p>
          )}
        </DetailRow>

        <DetailRow title="Call Us" Icon={PhoneIcon}>
          {contactPhone ? (
            <a href={`tel:${contactPhone.tel}`} className={detailLink}>
              {contactPhone.display}
            </a>
          ) : (
            <p className={pending}>Our phone number will be published here soon.</p>
          )}
        </DetailRow>

        <DetailRow title="Visit Our Office" Icon={MapPinIcon}>
          {officeAddress ? (
            <>
              <address className="mt-1 text-base leading-relaxed break-words text-ivory not-italic">
                {officeAddress.map((line) => (
                  <span key={line} className="block">
                    {line}
                  </span>
                ))}
              </address>
              <a
                href={mapsSearchUrl(officeAddress)}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex min-h-11 items-center rounded-sm text-[0.9375rem] font-medium text-gold-soft underline-offset-4 hover:underline focus-visible:outline-gold"
              >
                Open in Google Maps<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </>
          ) : (
            <p className={pending}>Our office address will be published here soon.</p>
          )}
        </DetailRow>
      </ul>

      <div className="mt-8 border-t border-gold/20 pt-7">
        <h3 id="contact-social-title" className="font-sans text-lg font-medium text-ivory">
          Connect With Us
        </h3>
        <ul aria-labelledby="contact-social-title" className="mt-4 flex flex-wrap gap-3">
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
        {hasPendingSocial && <p className={cn(pending, "mt-4")}>Our official channels are coming soon.</p>}
      </div>
    </div>
  );
}
