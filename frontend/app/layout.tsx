import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { config } from "@/lib/config";

import "./globals.css";

/**
 * The one typeface for the whole site, headings included. next/font self-hosts
 * it and generates the "__Plus_Jakarta_Sans_<hash>" family plus a size-matched
 * fallback, so text doesn't shift when the font loads.
 */
const jakarta = Plus_Jakarta_Sans({
  variable: "--font-sans-loaded",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  metadataBase: new URL(config.siteUrl),
  title: {
    default: `${config.siteName} | Trusted Matrimonial Service`,
    template: `%s | ${config.siteName}`,
  },
  description:
    "Find a compatible life partner through verified profiles, privacy controls and personal assistance.",
  openGraph: {
    type: "website",
    siteName: config.siteName,
    url: "/",
  },
};

export const viewport: Viewport = {
  themeColor: "#772333",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={jakarta.variable}>
      <body className="flex min-h-dvh flex-col">{children}</body>
    </html>
  );
}
