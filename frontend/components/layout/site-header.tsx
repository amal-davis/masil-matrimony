"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef, useState, useSyncExternalStore } from "react";

import { MobileNavDrawer } from "@/components/layout/mobile-nav-drawer";
import { SiteLogo } from "@/components/layout/site-logo";
import { MenuIcon, SearchIcon, UserIcon } from "@/components/ui/icons";
import { headerActions, mainNav } from "@/lib/site";
import { cn } from "@/lib/utils";

/** Pages whose first section is a dark hero the header can sit over transparently. */
const OVERLAY_PATHS = new Set(["/"]);

function subscribeToScroll(callback: () => void) {
  window.addEventListener("scroll", callback, { passive: true });
  return () => window.removeEventListener("scroll", callback);
}
const getScrolled = () => window.scrollY > 12;
const getServerScrolled = () => false;

const iconButton =
  "inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ivory transition-colors duration-200 hover:bg-white/10 hover:text-gold focus-visible:outline-gold";

export function SiteHeader() {
  const pathname = usePathname();
  const scrolled = useSyncExternalStore(subscribeToScroll, getScrolled, getServerScrolled);
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);

  const overlay = OVERLAY_PATHS.has(pathname);
  const transparent = overlay && !scrolled;

  return (
    <>
      <header
        className={cn(
          "inset-x-0 top-0 z-40 transition-[background-color,box-shadow] duration-300 motion-reduce:transition-none",
          overlay ? "fixed" : "sticky",
          transparent
            ? "bg-gradient-to-b from-wine-900/70 via-wine-900/25 to-transparent"
            : "bg-wine-800 shadow-[0_1px_0_rgba(210,165,74,0.25),0_8px_24px_rgba(31,5,11,0.18)]",
        )}
      >
        <div className="mx-auto flex h-18 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:grid lg:grid-cols-[1fr_auto_1fr] lg:px-8">
          <SiteLogo className="justify-self-start" />

          <nav aria-label="Main" className="hidden lg:block">
            <ul className="flex items-center gap-1 xl:gap-3">
              {mainNav.map((item) => {
                const current = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={current ? "page" : undefined}
                      className={cn(
                        "relative block rounded-sm px-3 py-2 text-[0.9375rem] font-medium tracking-[0.01em] whitespace-nowrap transition-colors duration-200 focus-visible:outline-gold",
                        "after:absolute after:inset-x-3 after:bottom-1 after:h-px after:origin-left after:bg-gold after:transition-transform after:duration-200 motion-reduce:after:transition-none",
                        current
                          ? "text-gold-soft after:scale-x-100"
                          : "text-ivory after:scale-x-0 hover:text-gold-soft hover:after:scale-x-100",
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="flex items-center gap-1 justify-self-end sm:gap-2">
            <Link href={headerActions.search.href} aria-label={headerActions.search.label} className={iconButton}>
              <SearchIcon className="size-[1.375rem]" />
            </Link>

            <Link
              href={headerActions.login.href}
              className="hidden h-10 items-center gap-2 rounded-md border border-gold/80 px-5 text-[0.9375rem] font-medium text-gold-soft transition-colors duration-200 hover:bg-gold hover:text-wine-900 focus-visible:outline-gold lg:inline-flex"
            >
              <UserIcon className="size-[1.125rem]" />
              {headerActions.login.label}
            </Link>

            <button
              ref={toggleRef}
              type="button"
              className={cn(iconButton, "lg:hidden")}
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label="Open menu"
              onClick={() => setOpen(true)}
            >
              <MenuIcon className="size-6" />
            </button>
          </div>
        </div>
      </header>

      <MobileNavDrawer id="mobile-nav" open={open} onClose={close} pathname={pathname} returnFocusRef={toggleRef} />
    </>
  );
}
