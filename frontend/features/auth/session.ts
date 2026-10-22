import { cookies } from "next/headers";

import { ACCESS_COOKIE, REFRESH_COOKIE, SIGNED_IN_COOKIE } from "./constants";
import { baseCookie, tokenExpiry, type TokenPair } from "./tokens";

/**
 * Server-side session storage (Server Actions and Route Handlers only).
 * Follows docs/architecture.md: API tokens live in HTTP-only, SameSite=Lax
 * cookies (Secure in production) and are never exposed to browser JavaScript.
 * proxy.ts renews an expiring access token before dashboard requests.
 */

export type { TokenPair };

export async function startSession({ access, refresh }: TokenPair) {
  const jar = await cookies();
  const refreshExpires = tokenExpiry(refresh);
  jar.set(ACCESS_COOKIE, access, { ...baseCookie, expires: tokenExpiry(access) });
  jar.set(REFRESH_COOKIE, refresh, { ...baseCookie, expires: refreshExpires });
  jar.set(SIGNED_IN_COOKIE, "1", { ...baseCookie, httpOnly: false, expires: refreshExpires });
}

/** Clear the session cookies and return the refresh token that was stored, if any. */
export async function endSession(): Promise<string | undefined> {
  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, SIGNED_IN_COOKIE]) jar.delete(name);
  return refresh;
}

/** The current access token, if the browser has one. */
export async function accessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}
