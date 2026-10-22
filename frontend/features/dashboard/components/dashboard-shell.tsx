"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { ChevronDownIcon, ChevronRightIcon, CloseIcon, HomeIcon, MenuIcon, UserIcon } from "@/components/ui/icons";
import { SIGNED_IN_COOKIE } from "@/features/auth/constants";
import { config } from "@/lib/config";
import { headerActions } from "@/lib/site";
import { cn } from "@/lib/utils";

import monogram from "@/public/images/masil-matrimony-monogram.png";

import { activeHref, bottomNav, breadcrumbsFor, dashboardNavGroups, type BadgeKey, type DashboardNavItem } from "../nav";
import { previewShellData } from "../preview";
import { DASHBOARD_PREVIEW } from "../preview-flag";
import type { ShellData } from "../types";
import { BellIcon, DotsIcon, GearIcon, LifebuoyIcon, LogoutIcon, SidebarIcon } from "./icons";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Preview builds: forget the display-only "signed in" flag set by the preview login. */
function clearPreviewSignIn() {
  document.cookie = `${SIGNED_IN_COOKIE}=; path=/; max-age=0; samesite=lax`;
}
const COLLAPSE_KEY = "mm-dashboard-sidebar-collapsed";

// --- Live data for the frame ----------------------------------------------

/** Avatar, name and badge counts, re-read after each navigation so badges follow changes. */
function useShellData(pathname: string): ShellData | null {
  // Preview builds use the sample data directly (static hosts have no route handlers).
  const [data, setData] = useState<ShellData | null>(() => (DASHBOARD_PREVIEW ? previewShellData() : null));
  useEffect(() => {
    if (DASHBOARD_PREVIEW) return;
    const controller = new AbortController();
    fetch("/dashboard/shell-data", { signal: controller.signal, cache: "no-store" })
      .then((response) => (response.ok && response.headers.get("content-type")?.includes("json") ? response.json() : null))
      .then((value: ShellData | null) => value && setData(value))
      .catch(() => {
        // The frame works without these; badges simply don't show.
      });
    return () => controller.abort();
  }, [pathname]);
  return data;
}

function badgeCount(data: ShellData | null, key?: BadgeKey): number {
  return key && data ? data[key] : 0;
}

// --- Small parts -----------------------------------------------------------

export function Avatar({ data, size = "md" }: { data: ShellData | null; size?: "md" | "lg" }) {
  const dimension = size === "lg" ? "size-11" : "size-9";
  const initials = (data?.name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span className={cn("relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-100 text-sm font-semibold text-wine-600 ring-1 ring-line", dimension)}>
      {data?.photoUrl ? (
        // Signed, short-lived URL (or a local sample image): nothing for the optimiser to cache.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={data.photoUrl} alt="" className="absolute inset-0 size-full object-cover object-top" />
      ) : initials ? (
        initials
      ) : (
        <UserIcon className="size-5" />
      )}
    </span>
  );
}

function CountBadge({ count, collapsed }: { count: number; collapsed?: boolean }) {
  if (count <= 0) return null;
  const text = count > 99 ? "99+" : String(count);
  return collapsed ? (
    <span aria-hidden="true" className="absolute top-1.5 right-1.5 size-2 rounded-full bg-wine-600 ring-2 ring-white" />
  ) : (
    <span aria-hidden="true" className="ml-auto inline-flex min-w-6 items-center justify-center rounded-full bg-wine-600 px-1.5 py-0.5 text-xs font-semibold text-white tabular-nums">
      {text}
    </span>
  );
}

function NavItemLink({
  item,
  active,
  collapsed,
  count,
  onNavigate,
}: {
  item: DashboardNavItem;
  active: boolean;
  collapsed: boolean;
  count: number;
  onNavigate?: () => void;
}) {
  const countLabel = count > 0 ? (item.badge === "awaitingReply" ? `, ${count} awaiting your reply` : `, ${count} unread`) : "";
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-10 items-center gap-3 rounded-lg text-[0.9375rem] font-medium transition-colors focus-visible:outline-wine-600",
        collapsed ? "justify-center px-0" : "px-3",
        active ? "bg-brand-50 text-wine-600" : "text-ink-muted hover:bg-mist hover:text-ink",
      )}
    >
      <span className={active ? "text-wine-600" : "text-ink-muted group-hover:text-ink"}>{item.icon}</span>
      <span className={collapsed ? "sr-only" : "truncate"}>
        {item.label}
        <span className="sr-only">{countLabel}</span>
      </span>
      <CountBadge count={count} collapsed={collapsed} />
      {collapsed && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-full z-50 ml-3 rounded-md bg-ink px-2.5 py-1.5 text-sm font-medium whitespace-nowrap text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 motion-reduce:transition-none"
        >
          {item.label}
          {count > 0 && ` (${count})`}
        </span>
      )}
    </Link>
  );
}

function NavGroups({
  current,
  collapsed = false,
  data,
  onNavigate,
}: {
  current?: string;
  collapsed?: boolean;
  data: ShellData | null;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      {dashboardNavGroups.map((group) => (
        <div key={group.label}>
          <p
            className={cn(
              // Sentence case: DESIGN.md keeps wide-tracked capitals for the wordmark alone.
              "mb-1.5 px-3 text-[0.8125rem] font-semibold text-ink-muted",
              collapsed && "sr-only",
            )}
          >
            {group.label}
          </p>
          {collapsed && <div aria-hidden="true" className="mx-auto mb-2 h-px w-6 bg-line" />}
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => (
              <li key={item.href}>
                <NavItemLink
                  item={item}
                  active={item.href === current}
                  collapsed={collapsed}
                  count={badgeCount(data, item.badge)}
                  onNavigate={onNavigate}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Brand({ collapsed, onClick }: { collapsed: boolean; onClick?: () => void }) {
  const [first, ...rest] = config.siteName.split(" ");
  return (
    <Link
      href="/dashboard"
      onClick={onClick}
      aria-label={`${config.siteName} member portal, overview`}
      className="flex min-w-0 items-center gap-3 rounded-md focus-visible:outline-gold"
    >
      <Image src={monogram} alt="" className="h-9 w-auto shrink-0 drop-shadow-[0_4px_8px_rgba(0,0,0,0.35)]" sizes="40px" />
      {!collapsed && (
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-lg font-semibold text-ivory">
            {first} <span className="font-normal text-gold-soft">{rest.join(" ")}</span>
          </span>
          <span className="text-xs text-ivory/70">Member Portal</span>
        </span>
      )}
    </Link>
  );
}

function LogoutForm({ className, collapsed = false }: { className?: string; collapsed?: boolean }) {
  // A preview has no session to end: leave it for the website instead.
  if (DASHBOARD_PREVIEW) {
    return (
      <Link
        href="/"
        onClick={clearPreviewSignIn}
        className={cn("group relative", className)}
        aria-label={collapsed ? "Exit preview" : undefined}
      >
        <LogoutIcon className="size-5 shrink-0" />
        {!collapsed && "Exit preview"}
      </Link>
    );
  }
  return (
    <form method="post" action={headerActions.logout.href}>
      <button type="submit" className={cn("group relative", className)} aria-label={collapsed ? "Log out" : undefined}>
        <LogoutIcon className="size-5 shrink-0" />
        {!collapsed && "Log out"}
      </button>
    </form>
  );
}

// --- Account menu ----------------------------------------------------------

function AccountMenu({ data }: { data: ShellData | null }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const choose = () => setOpen(false);

  // Close on outside clicks and Escape (choosing an item closes it too).
  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
      const index = items.indexOf(document.activeElement as HTMLElement);
      const next = event.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
      items[next]?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const item =
    "flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-[0.9375rem] text-ink transition-colors hover:bg-mist focus-visible:bg-mist focus-visible:outline-none";

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="account-menu"
        className="flex h-11 items-center gap-2.5 rounded-full py-1 pr-2 pl-1 transition-colors hover:bg-mist focus-visible:outline-wine-600 sm:pr-3"
      >
        <Avatar data={data} />
        <span className="hidden max-w-36 truncate text-sm font-semibold text-ink md:block">{data?.name ?? "My account"}</span>
        <ChevronDownIcon className={cn("hidden size-4 text-ink-muted transition-transform md:block", open && "rotate-180")} />
        <span className="sr-only md:hidden">Account menu</span>
      </button>

      {open && (
        <div
          ref={menuRef}
          id="account-menu"
          role="menu"
          aria-label="Account"
          className="absolute top-full right-0 z-50 mt-2 w-[min(17rem,calc(100vw-1.5rem))] rounded-xl border border-line bg-white p-2 shadow-[0_12px_32px_rgba(36,26,28,0.14)]"
        >
          <div className="flex items-center gap-3 border-b border-line px-3 pt-2 pb-3">
            <Avatar data={data} size="lg" />
            <div className="min-w-0">
              <p className="truncate font-semibold">{data?.name ?? "Member"}</p>
              <p className="truncate text-sm text-ink-muted">
                {data?.profileCode ?? "Profile not created"}
                {data?.membership && ` · ${data.membership}`}
              </p>
            </div>
          </div>
          <div className="flex flex-col py-1.5">
            <Link role="menuitem" onClick={choose} href="/dashboard/my-profile" className={item}>
              <UserIcon className="size-5 text-ink-muted" /> My Profile
            </Link>
            <Link role="menuitem" onClick={choose} href="/dashboard/settings" className={item}>
              <GearIcon className="size-5 text-ink-muted" /> Account Settings
            </Link>
            <Link role="menuitem" onClick={choose} href="/dashboard/help" className={item}>
              <LifebuoyIcon className="size-5 text-ink-muted" /> Help & Support
            </Link>
            <Link role="menuitem" onClick={choose} href="/" className={item}>
              <HomeIcon className="size-5 text-ink-muted" /> Back to website
            </Link>
          </div>
          <div className="border-t border-line pt-1.5">
            {DASHBOARD_PREVIEW ? (
              <Link
                role="menuitem"
                onClick={() => {
                  clearPreviewSignIn();
                  choose();
                }}
                href="/"
                className={item}
              >
                <LogoutIcon className="size-5 text-ink-muted" /> Exit preview
              </Link>
            ) : (
              <form method="post" action={headerActions.logout.href}>
                <button type="submit" role="menuitem" className={cn(item, "text-danger hover:bg-danger/5")}>
                  <LogoutIcon className="size-5" /> Log out
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Mobile drawer ---------------------------------------------------------

function Drawer({
  open,
  onClose,
  current,
  data,
  returnFocusRef,
}: {
  open: boolean;
  onClose: () => void;
  current?: string;
  data: ShellData | null;
  returnFocusRef: RefObject<HTMLButtonElement | null>;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open) closeRef.current?.focus();
    else if (wasOpen.current) returnFocusRef.current?.focus();
    wasOpen.current = open;
  }, [open, returnFocusRef]);

  useEffect(() => {
    if (!open) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") return onClose();
      if (event.key !== "Tab" || !panelRef.current) return;
      const items = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const desktop = window.matchMedia("(min-width: 64rem)");
    const onBreakpoint = (event: MediaQueryListEvent) => event.matches && onClose();
    document.addEventListener("keydown", onKeyDown);
    desktop.addEventListener("change", onBreakpoint);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", onKeyDown);
      desktop.removeEventListener("change", onBreakpoint);
    };
  }, [open, onClose]);

  return (
    <div className={cn("fixed inset-0 z-50 lg:hidden", !open && "pointer-events-none")} inert={!open}>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-wine-900/50 transition-opacity duration-300 motion-reduce:transition-none",
          open ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        ref={panelRef}
        id="dashboard-menu"
        role="dialog"
        aria-modal="true"
        aria-label="Dashboard menu"
        className={cn(
          "absolute inset-y-0 left-0 flex w-[min(19rem,86vw)] flex-col overflow-y-auto bg-white pb-[env(safe-area-inset-bottom)]",
          "transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none",
          open ? "translate-x-0 shadow-[12px_0_32px_rgba(31,5,11,0.25)]" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 shrink-0 items-center justify-between bg-wine-800 px-4">
          <Brand collapsed={false} onClick={onClose} />
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="inline-flex size-11 items-center justify-center rounded-md text-ivory hover:bg-white/10 focus-visible:outline-gold"
          >
            <CloseIcon className="size-6" />
          </button>
        </div>
        <nav aria-label="Dashboard" className="flex-1 px-3 py-5">
          <NavGroups current={current} data={data} onNavigate={onClose} />
        </nav>
        <div className="flex flex-col gap-1 border-t border-line p-3">
          <Link
            href="/"
            onClick={onClose}
            className="flex h-11 items-center gap-3 rounded-lg px-3 text-[0.9375rem] font-medium text-ink-muted hover:bg-mist hover:text-ink focus-visible:outline-wine-600"
          >
            <HomeIcon className="size-5 shrink-0" />
            Back to website
          </Link>
          <LogoutForm className="flex h-11 w-full items-center gap-3 rounded-lg px-3 text-[0.9375rem] font-medium text-danger hover:bg-danger/5 focus-visible:outline-wine-600" />
        </div>
      </div>
    </div>
  );
}

// --- Shell -----------------------------------------------------------------

/**
 * The member portal frame: a collapsible sidebar from `lg`, a compact top bar
 * with breadcrumbs, notifications and the account menu, and on phones an
 * off-canvas menu plus a bottom bar for the four most-used destinations.
 * It renders instantly; live values (badges, avatar) load alongside the page.
 */
export function DashboardShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const current = activeHref(pathname);
  const crumbs = breadcrumbsFor(pathname);
  const data = useShellData(pathname);
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const close = useCallback(() => setOpen(false), [setOpen]);
  const menuRef = useRef<HTMLButtonElement>(null);

  // Remember the desktop sidebar preference in this browser (a convenience only).
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reading a browser-only preference after hydration
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // Storage may be unavailable (private mode); the sidebar simply starts expanded.
    }
  }, []);
  const toggleCollapsed = () => {
    setCollapsed((value) => {
      try {
        window.localStorage.setItem(COLLAPSE_KEY, value ? "0" : "1");
      } catch {
        // Not saved; still works for this visit.
      }
      return !value;
    });
  };

  const unread = data?.unreadNotifications ?? 0;

  return (
    <div className="min-h-dvh bg-mist lg:flex">
      <a
        href="#dashboard-main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-md focus:bg-white focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-white transition-[width] duration-200 motion-reduce:transition-none lg:flex",
          collapsed ? "w-[4.75rem]" : "w-64",
        )}
      >
        <div className={cn("flex h-16 shrink-0 items-center bg-wine-800", collapsed ? "justify-center px-2" : "px-5")}>
          <Brand collapsed={collapsed} />
        </div>
        <nav aria-label="Dashboard" className={cn("flex-1 overflow-y-auto py-5", collapsed ? "px-3" : "px-3")}>
          <NavGroups current={current} collapsed={collapsed} data={data} />
        </nav>
        <div className="flex flex-col gap-1 border-t border-line p-3">
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex h-10 items-center gap-3 rounded-lg text-[0.9375rem] font-medium text-ink-muted transition-colors hover:bg-mist hover:text-ink focus-visible:outline-wine-600",
              collapsed ? "justify-center" : "px-3",
            )}
          >
            <SidebarIcon className="size-5 shrink-0" />
            {!collapsed && "Collapse"}
          </button>
          <LogoutForm
            collapsed={collapsed}
            className={cn(
              "flex h-10 w-full items-center gap-3 rounded-lg text-[0.9375rem] font-medium text-ink-muted transition-colors hover:bg-danger/5 hover:text-danger focus-visible:outline-wine-600",
              collapsed ? "justify-center" : "px-3",
            )}
          />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
          <div className="flex h-16 items-center gap-2 px-3 sm:px-6 lg:px-8">
            <button
              ref={menuRef}
              type="button"
              onClick={() => setOpen(true)}
              aria-label="Open dashboard menu"
              aria-expanded={open}
              aria-controls="dashboard-menu"
              className="inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ink hover:bg-mist focus-visible:outline-wine-600 lg:hidden"
            >
              <MenuIcon className="size-6" />
            </button>

            <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
              <ol className="flex min-w-0 items-center gap-1.5 text-sm">
                {crumbs.map((crumb, index) => {
                  const last = index === crumbs.length - 1;
                  return (
                    <li key={`${crumb.label}-${index}`} className={cn("flex min-w-0 items-center gap-1.5", !last && "hidden sm:flex")}>
                      {crumb.href && !last ? (
                        <Link href={crumb.href} className="rounded-sm text-ink-muted hover:text-wine-600 focus-visible:outline-wine-600">
                          {crumb.label}
                        </Link>
                      ) : (
                        <span aria-current={last ? "page" : undefined} className={last ? "truncate font-semibold text-ink" : "text-ink-muted"}>
                          {crumb.label}
                        </span>
                      )}
                      {!last && <ChevronRightIcon aria-hidden="true" className="size-4 shrink-0 text-ink-muted/60" />}
                    </li>
                  );
                })}
              </ol>
            </nav>

            <div className="flex shrink-0 items-center gap-1 sm:gap-2">
              <Link
                href="/dashboard/notifications"
                aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
                className="relative inline-flex size-11 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-mist hover:text-ink focus-visible:outline-wine-600"
              >
                <BellIcon className="size-[1.375rem]" />
                {unread > 0 && (
                  <span
                    aria-hidden="true"
                    className="absolute top-1.5 right-1.5 inline-flex min-w-[1.125rem] items-center justify-center rounded-full bg-wine-600 px-1 text-[0.6875rem] leading-[1.125rem] font-semibold text-white ring-2 ring-white"
                  >
                    {unread > 9 ? "9+" : unread}
                  </span>
                )}
              </Link>
              <AccountMenu data={data} />
            </div>
          </div>
        </header>

        {DASHBOARD_PREVIEW && (
          <p className="border-b border-accent-400 bg-accent-100 px-4 py-2 text-center text-sm text-ink">
            <strong className="font-semibold">Design preview with sample data.</strong> This isn&apos;t a real member
            account, and nothing you do here is saved.
          </p>
        )}

        <main id="dashboard-main" className="flex-1 px-4 pt-6 pb-28 sm:px-6 lg:px-8 lg:pt-8 lg:pb-12">
          <div className="mx-auto w-full max-w-[80rem]">{children}</div>
        </main>
      </div>

      {/* One-handed navigation on phones and tablets */}
      <nav
        aria-label="Dashboard shortcuts"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        <ul className="grid grid-cols-5">
          {bottomNav.map((item) => {
            const active = item.href === current;
            const count = badgeCount(data, item.badge);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-16 flex-col items-center justify-center gap-1 text-xs font-medium focus-visible:-outline-offset-2 focus-visible:outline-wine-600",
                    active ? "text-wine-600" : "text-ink-muted hover:text-ink",
                  )}
                >
                  <span className={cn("flex h-7 w-12 items-center justify-center rounded-full", active && "bg-brand-50")}>
                    {item.icon}
                  </span>
                  {item.short ?? item.label}
                  {count > 0 && (
                    <>
                      <span aria-hidden="true" className="absolute top-2 left-[calc(50%+0.5rem)] size-2 rounded-full bg-wine-600 ring-2 ring-white" />
                      <span className="sr-only">, {count} awaiting your reply</span>
                    </>
                  )}
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-expanded={open}
              aria-controls="dashboard-menu"
              className="flex h-16 w-full flex-col items-center justify-center gap-1 text-xs font-medium text-ink-muted hover:text-ink focus-visible:-outline-offset-2 focus-visible:outline-wine-600"
            >
              <span className="flex h-7 w-12 items-center justify-center">
                <DotsIcon className="size-5" />
              </span>
              More
            </button>
          </li>
        </ul>
      </nav>

      <Drawer open={open} onClose={close} current={current} data={data} returnFocusRef={menuRef} />
    </div>
  );
}
