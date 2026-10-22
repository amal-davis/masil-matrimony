"use client";

import Link from "next/link";
import { useEffect, useRef, type RefObject } from "react";

import { SiteLogo } from "@/components/layout/site-logo";
import { CloseIcon, SearchIcon } from "@/components/ui/icons";
import { useSignedIn } from "@/features/auth/use-signed-in";
import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";
import { headerActions, mainNav } from "@/lib/site";
import { cn } from "@/lib/utils";

const action =
  "inline-flex h-12 items-center justify-center gap-2 rounded-md text-[0.9375rem] font-medium transition-colors focus-visible:outline-gold";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

type MobileNavDrawerProps = {
  id: string;
  open: boolean;
  onClose: () => void;
  pathname: string;
  /** Receives focus back when the drawer closes. */
  returnFocusRef: RefObject<HTMLElement | null>;
};

/** Left-side navigation drawer for viewports below `lg`. */
export function MobileNavDrawer({ id, open, onClose, pathname, returnFocusRef }: MobileNavDrawerProps) {
  // Dashboard preview builds (e.g. the GitHub Pages preview) link straight to the sample dashboard.
  const signedIn = useSignedIn() || DASHBOARD_PREVIEW;
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  // Focus in on open, back to the toggle on close.
  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
    } else if (wasOpen.current) {
      returnFocusRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open, returnFocusRef]);

  // While open: lock page scroll, close on Escape, keep Tab inside the panel.
  useEffect(() => {
    if (!open) return;

    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
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
    }

    // The drawer has no desktop layout, so close it if the viewport grows past `lg`.
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
          "absolute inset-0 bg-wine-900/60 transition-opacity duration-300 motion-reduce:transition-none",
          open ? "opacity-100" : "opacity-0",
        )}
      />

      <div
        ref={panelRef}
        id={id}
        role="dialog"
        aria-modal="true"
        aria-label="Main menu"
        className={cn(
          "absolute inset-y-0 left-0 flex w-[min(20rem,86vw)] flex-col overflow-y-auto bg-wine-800 text-ivory",
          "transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none",
          // The shadow only while open: when closed it would bleed in from the left edge.
          open
            ? "translate-x-0 shadow-[1px_0_0_rgba(210,165,74,0.25),12px_0_32px_rgba(31,5,11,0.35)]"
            : "-translate-x-full",
        )}
      >
        <div className="flex h-18 shrink-0 items-center justify-between gap-3 border-b border-gold/20 px-4">
          <SiteLogo onClick={onClose} />
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ivory transition-colors hover:bg-white/10 hover:text-gold focus-visible:outline-gold"
          >
            <CloseIcon className="size-6" />
          </button>
        </div>

        <nav aria-label="Main" className="flex-1 px-2 py-4">
          <ul className="flex flex-col">
            {mainNav.map((item) => {
              const current = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onClose}
                    aria-current={current ? "page" : undefined}
                    className={cn(
                      "flex min-h-14 items-center rounded-md px-3 text-base font-medium transition-colors focus-visible:outline-gold",
                      current ? "text-gold" : "text-ivory hover:bg-white/5 hover:text-gold-soft",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex flex-col gap-3 border-t border-gold/20 p-4">
          <Link
            href={headerActions.search.href}
            onClick={onClose}
            className={cn(action, "border border-gold text-gold-soft hover:bg-gold hover:text-wine-900")}
          >
            <SearchIcon className="size-5" />
            {headerActions.search.label}
          </Link>
          {signedIn ? (
            <>
              <Link
                href={headerActions.dashboard.href}
                onClick={onClose}
                className={cn(action, "bg-gold text-wine-900 hover:bg-gold-soft")}
              >
                {headerActions.dashboard.label}
              </Link>
              {!DASHBOARD_PREVIEW && (
                <form method="post" action={headerActions.logout.href} className="flex flex-col">
                  <button type="submit" className={cn(action, "text-ivory hover:bg-white/10")}>
                    {headerActions.logout.label}
                  </button>
                </form>
              )}
            </>
          ) : (
            <Link
              href={headerActions.login.href}
              onClick={onClose}
              className={cn(action, "bg-gold text-wine-900 hover:bg-gold-soft")}
            >
              {headerActions.login.label}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
