import { cookies } from "next/headers";

import { ACCESS_COOKIE, PENDING_EMAIL_COOKIE, REFRESH_COOKIE, REMEMBER_COOKIE } from "./constants";
import { sessionCookies, SESSION_COOKIE_NAMES, type TokenPair } from "./tokens";

/**
 * Server-side session storage (Server Actions and Route Handlers only).
 * Follows docs/architecture.md: API tokens live in HTTP-only, SameSite=Lax
 * cookies (Secure in production) and are never exposed to browser JavaScript.
 * proxy.ts renews an expiring access token before dashboard requests.
 */

export type { TokenPair };

/** Store a new session. `remember` keeps it after the browser closes (see REMEMBER_COOKIE). */
export async function startSession(tokens: TokenPair, { remember }: { remember: boolean }) {
  const jar = await cookies();
  if (!remember) jar.delete(REMEMBER_COOKIE);
  for (const { name, value, options } of sessionCookies(tokens, remember)) jar.set(name, value, options);
}

/** Clear the session cookies and return the refresh token that was stored, if any. */
export async function endSession(): Promise<string | undefined> {
  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  for (const name of SESSION_COOKIE_NAMES) jar.delete(name);
  return refresh;
}

/** The current access token, if the browser has one. */
export async function accessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** The address waiting for verification on this browser (PENDING_EMAIL_COOKIE), if any. */
export async function pendingEmail(): Promise<string | undefined> {
  const value = (await cookies()).get(PENDING_EMAIL_COOKIE)?.value;
  return value && value.length <= 254 && EMAIL_PATTERN.test(value) ? value : undefined;
}
