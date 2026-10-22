import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";

export const metadata: Metadata = {
  title: { default: "My Dashboard", template: "%s | My Dashboard" },
  // Private member pages are never indexed.
  robots: { index: false, follow: false },
};

/** Member area: its own compact shell instead of the public site header and footer. Guarded by proxy.ts. */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <DashboardShell>{children}</DashboardShell>;
}
