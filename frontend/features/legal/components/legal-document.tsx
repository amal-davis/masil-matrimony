import Link from "next/link";
import type { ReactNode } from "react";

import { Container } from "@/components/ui/container";
import { cn } from "@/lib/utils";

import { formatLegalDate, legalConfig, pendingDecisions, type PendingDecision } from "../config";

/** One numbered section of a legal document. `id` is its anchor (#id) and must be unique on the page. */
export interface LegalSection {
  id: string;
  title: string;
  body: ReactNode;
}

const textLink =
  "rounded-sm font-medium text-wine-600 underline underline-offset-4 transition-colors hover:text-wine-800 focus-visible:outline-wine-600";

// ---------------------------------------------------------------------------
// Prose building blocks used by the document content files
// ---------------------------------------------------------------------------

export function P({ children }: { children: ReactNode }) {
  return <p>{children}</p>;
}

export function H3({ children }: { children: ReactNode }) {
  return <h3 className="pt-2 text-lg font-semibold text-ink">{children}</h3>;
}

export function List({ items, ordered = false }: { items: ReactNode[]; ordered?: boolean }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={cn("flex flex-col gap-2 pl-6", ordered ? "list-decimal" : "list-disc marker:text-wine-600")}>
      {items.map((item, index) => (
        <li key={index} className="pl-1">
          {item}
        </li>
      ))}
    </Tag>
  );
}

/** Internal link in running text. */
export function A({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={textLink}>
      {children}
    </Link>
  );
}

/**
 * A decision the owner has not made yet (features/legal/config.ts). Clearly
 * marked on the page so it can't be mistaken for an agreed policy.
 */
export function Pending({ id }: { id: PendingDecision }) {
  return (
    <span
      data-pending={id}
      className="rounded-sm border border-dashed border-accent-400 bg-accent-100 px-1.5 py-0.5 font-medium text-ink [box-decoration-break:clone]"
    >
      To be confirmed: {pendingDecisions[id]}
    </span>
  );
}

/** The official support and grievance contacts, or pending notes for whichever are missing. */
export function SupportContacts() {
  const officer = legalConfig.grievanceOfficer;
  return (
    <List
      items={[
        <>
          Email: <Owner value={legalConfig.email} pending="email" />
        </>,
        <>
          Phone: <Owner value={legalConfig.phone?.display} pending="phone" />
        </>,
        <>
          Address: <Owner value={legalConfig.address?.join(", ")} pending="address" />
        </>,
        <>
          Grievance Officer:{" "}
          <Owner value={officer && `${officer.name}, ${officer.designation}, ${officer.email}`} pending="grievanceOfficer" />
        </>,
      ]}
    />
  );
}

/** A configured value, or its pending note while it is still missing. */
export function Owner({ value, pending }: { value: string | null | undefined; pending: PendingDecision }) {
  return value ? <>{value}</> : <Pending id={pending} />;
}

// ---------------------------------------------------------------------------
// Page layout
// ---------------------------------------------------------------------------

function TableOfContents({ sections, className }: { sections: LegalSection[]; className?: string }) {
  return (
    <ol className={cn("flex flex-col text-[0.9375rem]", className)}>
      {sections.map((section, index) => (
        <li key={section.id}>
          <a
            href={`#${section.id}`}
            className="flex min-h-11 items-center gap-2.5 rounded-sm py-1 text-ink-muted transition-colors hover:text-wine-600 focus-visible:outline-wine-600 lg:min-h-9"
          >
            <span className="w-6 shrink-0 text-right text-sm tabular-nums text-ink-muted/80">{index + 1}.</span>
            <span className="min-w-0">{section.title}</span>
          </a>
        </li>
      ))}
    </ol>
  );
}

/**
 * Shared layout for the Privacy Policy and the Terms & Conditions: title,
 * last-updated date, a draft notice until the documents are approved, a table
 * of contents (collapsible on phones, sticky beside the text on desktops),
 * numbered sections and links to the related pages.
 */
export function LegalDocument({
  document,
  eyebrow,
  title,
  intro,
  sections,
  related,
}: {
  /** Which entry of legalConfig.lastUpdated dates this document. */
  document: keyof typeof legalConfig.lastUpdated;
  eyebrow: string;
  title: string;
  intro: ReactNode;
  sections: LegalSection[];
  related: { label: string; href: string; description: string }[];
}) {
  const lastUpdated = legalConfig.lastUpdated[document];

  return (
    <article aria-labelledby="legal-title">
      <header className="border-b border-line bg-mist">
        <Container className="py-10 sm:py-14 lg:py-16">
          <p className="text-sm font-medium tracking-[0.12em] text-wine-600 uppercase">{eyebrow}</p>
          <h1 id="legal-title" className="mt-3 text-3xl font-semibold text-balance sm:text-4xl lg:text-5xl">
            {title}
          </h1>
          <div className="mt-4 max-w-3xl text-lg leading-relaxed text-pretty text-ink-muted">{intro}</div>
          <p className="mt-5 text-[0.9375rem] text-ink-muted">
            Last updated: <time dateTime={lastUpdated}>{formatLegalDate(lastUpdated)}</time>
          </p>
        </Container>
      </header>

      <Container className="py-10 sm:py-12 lg:py-16">
        <div className="lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-14">
          {/* Desktop: sticky contents beside the text. */}
          <nav aria-labelledby="toc-title" className="hidden lg:block">
            <div className="sticky top-28 max-h-[calc(100dvh-8rem)] overflow-y-auto pb-4">
              <h2 id="toc-title" className="text-sm font-semibold tracking-[0.08em] text-ink uppercase">
                Contents
              </h2>
              <TableOfContents sections={sections} className="mt-3" />
            </div>
          </nav>

          <div className="min-w-0 max-w-3xl">
            {!legalConfig.approvedForPublication && (
              <div
                role="note"
                className="mb-10 rounded-md border border-accent-400 bg-accent-100 px-5 py-4 text-[0.9375rem] leading-relaxed text-ink"
              >
                <p className="font-semibold">Draft for review: not yet in effect</p>
                <p className="mt-1">
                  This document is being finalised and reviewed. Items marked &ldquo;To be confirmed&rdquo; have not been
                  decided yet. Please <A href="/contact">contact us</A> if you have a question in the meantime.
                </p>
              </div>
            )}

            {/* Phones and tablets: collapsible contents above the text. */}
            <details className="group mb-10 rounded-md border border-line bg-white lg:hidden">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 rounded-md px-4 font-semibold text-ink focus-visible:outline-wine-600 [&::-webkit-details-marker]:hidden">
                Contents
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="size-5 shrink-0 text-wine-600 transition-transform group-open:rotate-180"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
                    clipRule="evenodd"
                  />
                </svg>
              </summary>
              <nav aria-label="Contents" className="border-t border-line px-2 pb-2">
                <TableOfContents sections={sections} />
              </nav>
            </details>

            <div className="flex flex-col gap-12 text-base leading-[1.75] text-ink [overflow-wrap:anywhere] sm:text-[1.0625rem]">
              {sections.map((section, index) => (
                <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`} className="scroll-mt-28">
                  <h2 id={`${section.id}-title`} className="text-xl leading-snug font-semibold text-balance sm:text-2xl">
                    <span className="mr-2 text-wine-600 tabular-nums">{index + 1}.</span>
                    {section.title}
                  </h2>
                  <div className="mt-4 flex flex-col gap-4">{section.body}</div>
                </section>
              ))}
            </div>

            <aside aria-labelledby="related-title" className="mt-14 border-t border-line pt-8">
              <h2 id="related-title" className="text-lg font-semibold">
                Related pages
              </h2>
              <ul className="mt-4 grid gap-4 sm:grid-cols-2">
                {related.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="flex h-full flex-col rounded-md border border-line bg-white px-5 py-4 transition-colors hover:border-wine-600 focus-visible:outline-wine-600"
                    >
                      <span className="font-semibold text-wine-600">{item.label}</span>
                      <span className="mt-1 text-[0.9375rem] leading-relaxed text-ink-muted">{item.description}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </div>
      </Container>
    </article>
  );
}
