import { accessToken } from "@/features/auth/session";
import { DASHBOARD_PREVIEW, PREVIEW_ACTION_MESSAGE } from "@/features/dashboard/preview-flag";
import { getApiBaseUrl } from "@/lib/config";

/** Same-site check: Route Handlers don't get Server Actions' built-in Origin check. */
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

const json = (body: unknown, status: number) => Response.json(body, { status });

/**
 * POST /dashboard/photos/upload: forwards one photo (multipart field `photo`)
 * to the API as the signed-in member. A Route Handler rather than a Server
 * Action so the browser can show upload progress. The API validates and
 * re-encodes the image; nothing is stored here.
 */
export async function POST(request: Request) {
  if (!isSameOrigin(request)) return json({ detail: "Forbidden." }, 403);
  // UI preview builds never store anything.
  if (DASHBOARD_PREVIEW) return json({ detail: PREVIEW_ACTION_MESSAGE }, 503);

  const token = await accessToken();
  if (!token) return json({ detail: "Your session has ended. Please sign in again.", code: "signed_out" }, 401);

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return json({ detail: "The upload couldn't be read. Please try again." }, 400);
  }
  const photo = form.get("photo");
  if (!(photo instanceof File) || photo.size === 0) return json({ photo: ["Choose a photo to upload."] }, 400);

  const upstream = new FormData();
  upstream.append("photo", photo, "upload");
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/profiles/me/photos/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      body: upstream,
      signal: AbortSignal.timeout(60_000),
    });
  } catch {
    return json({ detail: "We couldn't reach our server. Please try again." }, 502);
  }

  const body = await response.json().catch(() => ({ detail: "Upload failed. Please try again." }));
  return json(body, response.status);
}
