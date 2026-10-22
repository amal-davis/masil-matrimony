import Link from "next/link";
import type { ReactNode } from "react";

import { ChevronLeftIcon, ChevronRightIcon, InfoIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/*
 * The member portal's component kit. Tokens come from app/globals.css
 * (wine, gold, ink, mist, line…); these components fix how they're combined:
 * 12px radius panels with 1px borders and no resting shadow, 8px controls,
 * 44px minimum touch targets, wine-600 for actions and focus.
 */

// --- Buttons ---------------------------------------------------------------

const buttonBase =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-[0.9375rem] font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-55";

export const primaryButton = cn(buttonBase, "bg-wine-600 text-white hover:bg-wine-800 focus-visible:outline-wine-600");
export const secondaryButton = cn(
  buttonBase,
  "border border-line bg-white text-ink hover:border-field-line hover:bg-mist focus-visible:outline-wine-600",
);
export const quietButton = cn(buttonBase, "px-3 text-wine-600 hover:bg-brand-50 focus-visible:outline-wine-600");
export const dangerButton = cn(
  buttonBase,
  "border border-danger/40 bg-white text-danger hover:bg-danger/5 focus-visible:outline-danger",
);
export const successButton = cn(buttonBase, "bg-success text-white hover:bg-success/90 focus-visible:outline-success");

// --- Page structure --------------------------------------------------------

/** Title, one-line description and the page's main actions. One per page. */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between lg:mb-8">
      <div className="min-w-0">
        <h1 className="text-2xl leading-tight font-semibold tracking-tight sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-1.5 max-w-[65ch] text-[0.9375rem] text-pretty text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/** A white panel. With a title it gets a header row (title, optional description and actions). */
export function Card({
  title,
  titleId,
  description,
  actions,
  className,
  bodyClassName,
  children,
}: {
  title?: string;
  titleId?: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  const hasHeader = Boolean(title || actions);
  return (
    <section
      aria-labelledby={title ? titleId : undefined}
      className={cn("min-w-0 rounded-xl border border-line bg-white", !hasHeader && "p-5 sm:p-6", className)}
    >
      {hasHeader ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line px-5 py-4 sm:px-6">
            <div className="min-w-0">
              {title && (
                <h2 id={titleId} className="text-base font-semibold sm:text-[1.0625rem]">
                  {title}
                </h2>
              )}
              {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
            </div>
            {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
          </div>
          {/* bodyClassName replaces the default padding (e.g. "p-0" for edge-to-edge lists). */}
          <div className={bodyClassName ?? "p-5 sm:p-6"}>{children}</div>
        </>
      ) : (
        children
      )}
    </section>
  );
}

// --- Status ----------------------------------------------------------------

const badgeTones = {
  neutral: "bg-surface-muted text-ink-muted ring-line",
  info: "bg-accent-100 text-[#7a5a13] ring-accent-400/60",
  success: "bg-success/10 text-success ring-success/30",
  danger: "bg-danger/10 text-danger ring-danger/30",
  brand: "bg-brand-50 text-wine-600 ring-brand-200",
};

export type BadgeTone = keyof typeof badgeTones;

/** A status label: a dot plus text, never colour alone. Used for every status in the portal. */
export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.8125rem] font-medium whitespace-nowrap ring-1 ring-inset",
        badgeTones[tone],
      )}
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

export function ProgressBar({
  value,
  label,
  showValue = true,
  className,
}: {
  value: number;
  label: string;
  showValue?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-ink">{label}</span>
        {showValue && <span className="font-semibold text-wine-600 tabular-nums">{value}%</span>}
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted"
      >
        <div className="h-full rounded-full bg-wine-600 transition-[width] motion-reduce:transition-none" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

/** A headline number that links to where it comes from. Numbers are always real counts. */
export function StatCard({
  label,
  value,
  href,
  icon,
  note,
  emphasis = false,
}: {
  label: string;
  value: number;
  href: string;
  icon: ReactNode;
  note?: string;
  emphasis?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex min-w-0 flex-col justify-between gap-4 rounded-xl border border-line bg-white p-5 transition-colors hover:border-field-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wine-600"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-ink-muted">{label}</span>
        <span aria-hidden="true" className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-wine-600">
          {icon}
        </span>
      </div>
      <div>
        <span className="block text-3xl leading-none font-semibold tracking-tight text-ink tabular-nums">{value}</span>
        <span className={cn("mt-2 flex items-center gap-1 text-sm", emphasis ? "font-medium text-wine-600" : "text-ink-muted")}>
          {note ?? "View all"}
          <ChevronRightIcon aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
        </span>
      </div>
    </Link>
  );
}

// --- Navigation within a page ---------------------------------------------

/** Filter or section tabs that are links (the URL holds the state, so refresh and back work). */
export function LinkTabs({
  label,
  tabs,
  className,
}: {
  label: string;
  tabs: { href: string; label: string; active: boolean; count?: number }[];
  className?: string;
}) {
  return (
    <nav aria-label={label} className={cn("-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0", className)}>
      <ul className="flex w-max gap-1 rounded-lg border border-line bg-white p-1">
        {tabs.map((tab) => (
          <li key={tab.href}>
            <Link
              href={tab.href}
              aria-current={tab.active ? "page" : undefined}
              className={cn(
                "inline-flex min-h-9 items-center gap-2 rounded-md px-3.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-wine-600",
                tab.active ? "bg-wine-600 text-white" : "text-ink-muted hover:bg-mist hover:text-ink",
              )}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className={cn("rounded-full px-1.5 text-xs tabular-nums", tab.active ? "bg-white/20" : "bg-surface-muted")}>
                  {tab.count}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

// --- Feedback --------------------------------------------------------------

export function EmptyState({
  icon,
  title,
  children,
  action,
  compact = false,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={cn("rounded-xl border border-dashed border-field-line/50 bg-white text-center", compact ? "px-5 py-8" : "px-6 py-14")}>
      {icon && (
        <span aria-hidden="true" className="mx-auto flex size-12 items-center justify-center rounded-full bg-brand-50 text-wine-600">
          {icon}
        </span>
      )}
      <h2 className="mt-4 text-base font-semibold sm:text-lg">{title}</h2>
      {children && <div className="mx-auto mt-1.5 max-w-[48ch] text-[0.9375rem] text-pretty text-ink-muted">{children}</div>}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

/** An inline message. `role` makes errors and confirmations announce themselves. */
export function Notice({
  tone = "info",
  children,
  role,
  className,
}: {
  tone?: "info" | "success" | "danger";
  children: ReactNode;
  role?: "alert" | "status";
  className?: string;
}) {
  const tones = {
    info: "border-accent-400/70 bg-accent-100/70",
    success: "border-success/30 bg-success/5",
    danger: "border-danger/30 bg-danger/5",
  };
  return (
    <div role={role} className={cn("flex items-start gap-2.5 rounded-lg border px-4 py-3 text-[0.9375rem] text-ink", tones[tone], className)}>
      <InfoIcon className={cn("mt-0.5 size-5 shrink-0", tone === "danger" ? "text-danger" : tone === "success" ? "text-success" : "text-accent-600")} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Previous/next links that keep the other query parameters. */
export function Pagination({
  page,
  count,
  pageSize = 20,
  basePath,
  params = {},
}: {
  page: number;
  count: number;
  pageSize?: number;
  basePath: string;
  params?: Record<string, string | undefined>;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;
  const href = (target: number) => {
    const query = new URLSearchParams(
      Object.entries({ ...params, page: target > 1 ? String(target) : undefined }).filter(
        (entry): entry is [string, string] => Boolean(entry[1]),
      ),
    ).toString();
    return query ? `${basePath}?${query}` : basePath;
  };
  return (
    <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-4">
      {page > 1 ? (
        <Link href={href(page - 1)} className={secondaryButton}>
          <ChevronLeftIcon className="size-4" /> Previous
        </Link>
      ) : (
        <span />
      )}
      <p className="text-sm text-ink-muted">
        Page {page} of {pages}
      </p>
      {page < pages ? (
        <Link href={href(page + 1)} className={secondaryButton}>
          Next <ChevronRightIcon className="size-4" />
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}

/** A grey block standing in for content while it loads. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-surface-muted motion-reduce:animate-none", className)} />;
}

/** Page number from `?page=`, defaulting to 1 for anything invalid. */
export function pageParam(value: string | string[] | undefined): number {
  const page = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(page) && page > 0 ? page : 1;
}
