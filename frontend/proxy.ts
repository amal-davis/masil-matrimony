import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, loginUrl, REFRESH_COOKIE, REMEMBER_COOKIE } from "@/features/auth/constants";
import { isExpiring, sessionCookies, SESSION_COOKIE_NAMES, type TokenPair } from "@/features/auth/tokens";
import { DASHBOARD_PREVIEW } from "@/features/dashboard/preview-flag";
import { getApiBaseUrl } from "@/lib/config";

/**
 * Guards the member dashboard (pages, Server Actions and the photo upload
 * handler under /dashboard) and keeps sessions fresh on member profile pages:
 *
 * - no session on /dashboard → redirect to /login?next=<this page>
 * - access token expiring    → exchange the refresh token with the API, set the
 *   new cookies on the response and on this request, so the page renders with
 *   the fresh token (keeping the member's "Keep me signed in" choice)
 *
 * This is the "optimistic" check: the API still authorises every request.
 */
export async function proxy(request: NextRequest) {
  // UI preview builds show only fictional sample data and never call the API, so no login is needed.
  if (DASHBOARD_PREVIEW) return NextResponse.next();

  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  // Member profile pages are public routes: renew a session there, but never force a login.
  const required = request.nextUrl.pathname === "/dashboard" || request.nextUrl.pathname.startsWith("/dashboard/");

  if (access && !isExpiring(access)) return NextResponse.next();
  if (!refresh && !required) return NextResponse.next();

  const tokens = refresh ? await refreshTokens(refresh) : null;
  if (!tokens) return required ? toLogin(request) : NextResponse.next();

  // Make the new tokens visible to the page rendering this request...
  request.cookies.set(ACCESS_COOKIE, tokens.access);
  request.cookies.set(REFRESH_COOKIE, tokens.refresh);
  const response = NextResponse.next({ request: { headers: request.headers } });
  // ...and store them in the browser.
  const persistent = request.cookies.has(REMEMBER_COOKIE);
  for (const { name, value, options } of sessionCookies(tokens, persistent)) response.cookies.set(name, value, options);
  return response;
}

async function refreshTokens(refresh: string): Promise<TokenPair | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as Partial<TokenPair>;
    return data.access && data.refresh ? { access: data.access, refresh: data.refresh } : null;
  } catch {
    return null;
  }
}

function toLogin(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  // Server Actions and uploads are POSTs: send them back to the page, not to a redirect target they can't follow.
  const target = request.method === "GET" ? `${pathname}${search}` : "/dashboard";
  const response = NextResponse.redirect(new URL(loginUrl(target), request.url));
  for (const name of SESSION_COOKIE_NAMES) response.cookies.delete(name);
  return response;
}

export const config = {
  matcher: ["/dashboard", "/dashboard/:path*", "/profile/:path*"],
};
