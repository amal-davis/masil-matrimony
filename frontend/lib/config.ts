import { z } from "zod";

/**
 * Public runtime configuration, validated once at startup.
 *
 * NEXT_PUBLIC_* values are inlined into the browser bundle at build time, so
 * they must be referenced statically (process.env.NEXT_PUBLIC_X) and must
 * never contain secrets.
 */
const publicConfigSchema = z.object({
  apiBaseUrl: z.url({ message: "NEXT_PUBLIC_API_BASE_URL must be an absolute URL" }),
  siteUrl: z.url({ message: "NEXT_PUBLIC_SITE_URL must be an absolute URL" }),
  siteName: z.string().trim().min(1),
});

const parsed = publicConfigSchema.safeParse({
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  siteName: process.env.NEXT_PUBLIC_SITE_NAME ?? "Maasil Matrimony",
});

if (!parsed.success) {
  const issues = parsed.error.issues.map((issue) => `- ${issue.message}`).join("\n");
  throw new Error(
    `Invalid frontend configuration. Copy frontend/.env.example to frontend/.env.local.\n${issues}`,
  );
}

const stripTrailingSlash = (url: string) => url.replace(/\/+$/, "");

export const config = {
  apiBaseUrl: stripTrailingSlash(parsed.data.apiBaseUrl),
  siteUrl: stripTrailingSlash(parsed.data.siteUrl),
  siteName: parsed.data.siteName,
} as const;

/**
 * Base URL for API calls. Server-side code may use a private network address
 * (API_INTERNAL_BASE_URL, e.g. a Docker service name); browsers always use the
 * public URL.
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined" && process.env.API_INTERNAL_BASE_URL) {
    return stripTrailingSlash(process.env.API_INTERNAL_BASE_URL);
  }
  return config.apiBaseUrl;
}
