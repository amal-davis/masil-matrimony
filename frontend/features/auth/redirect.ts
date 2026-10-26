import { DEFAULT_AFTER_LOGIN, LOGIN_PATH, VERIFY_MOBILE_PATH } from "./constants";

const ORIGIN = "http://same-origin.invalid";

/** Sign-in pages are never a destination after signing in. */
const AUTH_PATHS = new Set([LOGIN_PATH, VERIFY_MOBILE_PATH]);

/**
 * The `next` destination if it is a path on this site, otherwise the default.
 * Blocks open redirects such as "//evil.com", "/\\evil.com" and "https://evil.com".
 */
export function safeRedirectPath(next: unknown): string {
  if (typeof next !== "string" || next.length > 512 || !next.startsWith("/")) return DEFAULT_AFTER_LOGIN;
  // Backslashes and control characters are normalised by browsers into surprising URLs.
  if (/[\\\u0000-\u001f\u007f]/.test(next)) return DEFAULT_AFTER_LOGIN;

  let url: URL;
  try {
    url = new URL(next, ORIGIN);
  } catch {
    return DEFAULT_AFTER_LOGIN;
  }
  if (url.origin !== ORIGIN || AUTH_PATHS.has(url.pathname.replace(/\/+$/, ""))) return DEFAULT_AFTER_LOGIN;
  return `${url.pathname}${url.search}${url.hash}`;
}
