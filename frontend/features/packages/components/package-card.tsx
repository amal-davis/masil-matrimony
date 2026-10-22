import Link from "next/link";
import type { ComponentProps, ComponentType } from "react";

import { GemIcon, HomeIcon, UsersIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

import { formatInr, type MembershipPackage, type PackageId } from "../packages";
import { BenefitList } from "./benefit-list";

type Theme = {
  Icon: ComponentType<ComponentProps<"svg">>;
  card: string;
  /** Strip across the top of the card. */
  accent: string;
  header: string;
  kind: string;
  title: string;
  subtitle: string;
  muted: string;
  footer: string;
  cta: string;
};

/**
 * Each package differs by icon and service label as well as colour. Long text stays
 * on white (DESIGN.md "Read It On White"); only Royal's header and footer are wine.
 */
const themes: Record<PackageId, Theme> = {
  diamond: {
    Icon: GemIcon,
    card: "border-line",
    accent: "bg-accent-400",
    header: "bg-white border-line",
    kind: "border-accent-400 bg-accent-100 text-wine-600",
    title: "text-ink",
    subtitle: "text-wine-600",
    muted: "text-ink-muted",
    footer: "bg-white border-line",
    cta: "bg-wine-600 text-white hover:bg-wine-800 focus-visible:outline-wine-600",
  },
  platinum: {
    Icon: UsersIcon,
    card: "border-brand-200",
    accent: "bg-wine-600",
    header: "bg-brand-50 border-brand-200",
    kind: "border-wine-600 bg-wine-600 text-white",
    title: "text-ink",
    subtitle: "text-wine-600",
    muted: "text-ink-muted",
    footer: "bg-white border-line",
    cta: "bg-wine-600 text-white hover:bg-wine-800 focus-visible:outline-wine-600",
  },
  royal: {
    Icon: HomeIcon,
    card: "border-wine-600",
    accent: "bg-gold",
    header: "bg-wine-800 border-gold/30",
    kind: "border-gold/70 text-gold-soft",
    title: "text-ivory",
    subtitle: "text-gold-soft",
    muted: "text-ivory/85",
    footer: "bg-wine-800 border-gold/30",
    cta: "bg-gold text-wine-900 hover:bg-gold-soft focus-visible:outline-gold",
  },
};

/**
 * One package. From `md` the card is a three-row subgrid (header, details, action)
 * of the parent grid, so prices and buttons line up across cards in a row.
 */
export function PackageCard({ pkg }: { pkg: MembershipPackage }) {
  const theme = themes[pkg.id];
  const titleId = `package-${pkg.id}-title`;

  return (
    <li
      className={cn(
        "relative flex flex-col overflow-hidden rounded-xl border bg-white md:row-span-3 md:grid md:grid-rows-subgrid md:gap-0",
        theme.card,
        pkg.id === "royal" && "md:col-span-2 md:mt-6 lg:col-span-1 lg:mt-0",
      )}
    >
      <span aria-hidden="true" className={cn("absolute inset-x-0 top-0 h-1", theme.accent)} />

      {/* Name, description and price */}
      <div className={cn("flex flex-col border-b px-5 pt-7 pb-6 sm:px-7", theme.header)}>
        <p
          className={cn(
            "inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium",
            theme.kind,
          )}
        >
          <theme.Icon className="size-4" />
          {pkg.kind}
        </p>

        <h3 id={titleId} className={cn("mt-4 text-[1.75rem] leading-tight font-semibold", theme.title)}>
          {pkg.name}
          {pkg.subtitle && (
            <span className={cn("mt-1 block text-lg leading-snug font-medium", theme.subtitle)}>{pkg.subtitle}</span>
          )}
        </h3>
        {pkg.tagline && <p className={cn("mt-2 text-base italic", theme.muted)}>{pkg.tagline}</p>}
        <p className={cn("mt-3 max-w-[60ch] text-base leading-relaxed text-pretty", theme.muted)}>
          {pkg.description}
        </p>

        <div className="mt-auto pt-6">
          <p className={cn("text-[2.5rem] leading-none font-semibold tracking-tight tabular-nums", theme.title)}>
            {formatInr(pkg.price.amount)}
          </p>
          <p className={cn("mt-2 text-[0.9375rem] leading-relaxed font-medium", theme.subtitle)}>
            {pkg.price.taxNote}
          </p>
        </div>
      </div>

      {/* Facts, benefits, price summary and terms */}
      <div className="flex flex-col gap-6 px-5 py-6 sm:px-7">
        <dl className="divide-y divide-line rounded-lg border border-line">
          {pkg.facts.map((fact) => (
            <div key={fact.label} className="px-4 py-3">
              <dt className="text-sm text-ink-muted">{fact.label}</dt>
              <dd className="mt-0.5 text-base font-semibold text-ink">{fact.value}</dd>
            </div>
          ))}
        </dl>

        <div>
          <h4 className="text-base font-semibold text-ink">What&apos;s included</h4>
          <div className="mt-4">
            <BenefitList benefits={pkg.benefits} packageName={pkg.name} />
          </div>
        </div>

        <div className="mt-auto flex flex-col gap-4">
          <div className="rounded-lg border border-line px-4 pt-3 pb-4">
            <h4 className="text-base font-semibold text-ink">Price summary</h4>
            <dl className="mt-1 divide-y divide-line">
              {pkg.price.lines.map((line, index) => {
                const total = index === pkg.price.lines.length - 1;
                return (
                  <div key={line.label} className="flex items-baseline justify-between gap-4 py-2.5">
                    <dt className={cn("text-[0.9375rem]", total ? "font-semibold text-ink" : "text-ink-muted")}>
                      {line.label}
                    </dt>
                    <dd
                      className={cn(
                        "max-w-[60%] text-right text-[0.9375rem] text-ink tabular-nums",
                        total ? "font-semibold" : "font-medium",
                      )}
                    >
                      {typeof line.value === "number" ? formatInr(line.value) : line.value}
                    </dd>
                  </div>
                );
              })}
            </dl>
            {pkg.price.summaryNote && (
              <p className="mt-1 text-[0.9375rem] leading-relaxed text-ink-muted">{pkg.price.summaryNote}</p>
            )}
          </div>

          <div className="rounded-lg bg-mist px-4 py-3.5">
            <h4 className="text-base font-semibold text-ink">{pkg.terms.title}</h4>
            <p className="mt-1 text-[0.9375rem] leading-relaxed text-pretty text-ink">{pkg.terms.body}</p>
          </div>
        </div>
      </div>

      {/* Action */}
      <div className={cn("border-t px-5 py-5 sm:px-7", theme.footer)}>
        <Link
          href={pkg.cta.href}
          className={cn(
            "flex h-13 w-full items-center justify-center rounded-md px-6 text-base font-medium transition-colors duration-200 motion-reduce:transition-none",
            theme.cta,
          )}
        >
          {pkg.cta.label}
        </Link>
        <p className={cn("mt-2.5 text-center text-sm", pkg.id === "royal" ? "text-ivory/80" : "text-ink-muted")}>
          Opens our contact form to send an enquiry.
        </p>
      </div>
    </li>
  );
}
