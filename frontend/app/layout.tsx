import type { Metadata, Viewport } from "next";
import { Fraunces, Geist } from "next/font/google";

import { config } from "@/lib/config";

import "./globals.css";

const sans = Geist({ variable: "--font-sans-loaded", subsets: ["latin"] });
const display = Fraunces({ variable: "--font-display-loaded", subsets: ["latin"] });

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
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="flex min-h-dvh flex-col">{children}</body>
    </html>
  );
}
