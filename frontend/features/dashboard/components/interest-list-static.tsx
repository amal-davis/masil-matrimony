"use client";

import { useSearchParams } from "next/navigation";

import type { InterestItem } from "../types";
import { InterestList, validStatus } from "./interest-list";

/**
 * The interests list for the static GitHub Pages preview, where the server
 * can't read the query string: the status filter is applied in the browser to
 * the (sample) items instead. Render inside <Suspense>.
 */
export function StaticInterestList({ direction, items }: { direction: "received" | "sent"; items: InterestItem[] }) {
  const status = validStatus(direction, useSearchParams().get("status") ?? undefined);
  const results = status ? items.filter((item) => item.status === status) : items;
  return (
    <InterestList direction={direction} data={{ count: results.length, next: null, previous: null, results }} status={status} page={1} />
  );
}
