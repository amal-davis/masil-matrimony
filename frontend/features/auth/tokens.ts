/**
 * Token cookie helpers shared by the session code (Server Actions, Route
 * Handlers) and proxy.ts. No Next.js request APIs here, so both can use it.
 */

import { ACCESS_COOKIE, REFRESH_COOKIE, REMEMBER_COOKIE, SIGNED_IN_COOKIE } from "./constants";

export interface TokenPair {
  access: string;
  refresh: string;
}

/** The `exp` claim of a JWT as a Date. The signature is checked by the API, not here. */
export function tokenExpiry(token: string): Date | undefined {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(part));
    return typeof payload.exp === "number" ? new Date(payload.exp * 1000) : undefined;
  } catch {
    return undefined;
  }
}

/** True when the token expires within `marginMs` (or can't be read). */
export function isExpiring(token: string, marginMs = 30_000): boolean {
  const expires = tokenExpiry(token);
  return !expires || expires.getTime() - Date.now() < marginMs;
}

export const baseCookie = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
} as const;

/**
 * The cookies that hold a session. `persistent` ("Keep me signed in") makes them
 * last until the refresh token expires; otherwise they are browser-session cookies.
 * Either way the API's token lifetimes and blacklist still decide what is valid.
 */
export function sessionCookies({ access, refresh }: TokenPair, persistent: boolean) {
  const refreshExpires = tokenExpiry(refresh);
  const until = (expires: Date | undefined) => (persistent ? { expires } : {});
  return [
    { name: ACCESS_COOKIE, value: access, options: { ...baseCookie, ...until(tokenExpiry(access)) } },
    { name: REFRESH_COOKIE, value: refresh, options: { ...baseCookie, ...until(refreshExpires) } },
    { name: SIGNED_IN_COOKIE, value: "1", options: { ...baseCookie, httpOnly: false, ...until(refreshExpires) } },
    ...(persistent
      ? [{ name: REMEMBER_COOKIE, value: "1", options: { ...baseCookie, expires: refreshExpires } }]
      : []),
  ];
}

/** Every cookie a session may set, for clearing them all. */
export const SESSION_COOKIE_NAMES = [ACCESS_COOKIE, REFRESH_COOKIE, SIGNED_IN_COOKIE, REMEMBER_COOKIE];
