/**
 * Token cookie helpers shared by the session code (Server Actions, Route
 * Handlers) and proxy.ts. No Next.js request APIs here, so both can use it.
 */

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
