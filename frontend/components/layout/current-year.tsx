"use client";

import { useSyncExternalStore } from "react";

/** Set in next.config.ts when the site is built. */
const BUILD_YEAR = Number(process.env.NEXT_PUBLIC_BUILD_YEAR);

const subscribe = () => () => {};

/**
 * The current year. The server (and a static export) renders the build year;
 * after hydration the browser's clock takes over, so a page built in December
 * still says the right year in January. useSyncExternalStore reads the server
 * snapshot during hydration, so there is no mismatch.
 */
export function CurrentYear() {
  return useSyncExternalStore(
    subscribe,
    () => new Date().getFullYear(),
    () => BUILD_YEAR,
  );
}
