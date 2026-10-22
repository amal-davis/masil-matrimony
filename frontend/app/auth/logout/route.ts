import { endSession } from "@/features/auth/session";
import { api } from "@/lib/api/client";

/** True when the request was sent by a page on this site (blocks cross-site logout). */
function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  if (!origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

/**
 * POST /auth/logout: blacklist the refresh token in the API, clear the session
 * cookies and go to the home page. Posted by a plain form, so it works without JavaScript.
 */
export async function POST(request: Request) {
  if (!isSameOrigin(request)) {
    return new Response(null, { status: 403 });
  }

  const refresh = await endSession();
  if (refresh) {
    // The cookies are gone either way; an already-expired or blacklisted token is fine.
    await api.post("/auth/token/blacklist/", { refresh }, { cache: "no-store" }).catch(() => undefined);
  }
  return new Response(null, { status: 303, headers: { Location: "/" } });
}
