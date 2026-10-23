import { redirect } from "next/navigation";

import { DASHBOARD_PATH, loginUrl } from "@/features/auth/constants";
import { accessToken } from "@/features/auth/session";
import { api, ApiError } from "@/lib/api/client";
import type { ApiErrorBody } from "@/types/api";

import { DASHBOARD_PREVIEW, PREVIEW_ACTION_MESSAGE } from "./preview-flag";
import {
  previewAccount,
  previewMatches,
  previewMembership,
  previewNotifications,
  previewPage,
  previewPhotos,
  previewProfile,
  previewReceived,
  previewSent,
  previewShortlist,
  previewSummary,
} from "./preview";

import type {
  DashboardSummary,
  InterestItem,
  MembershipInfo,
  MemberCard,
  NotificationItem,
  OwnPhoto,
  OwnProfile,
  Paginated,
  ShortlistItem,
} from "./types";

/**
 * Server-side calls to the member API with the session's access token
 * (Server Components and Server Actions only). The token comes from the
 * HTTP-only cookie and is never sent to the browser.
 */

async function authHeaders(returnTo: string): Promise<HeadersInit> {
  const token = await accessToken();
  // proxy.ts normally catches this first; this covers a session ending mid-request.
  if (!token) redirect(loginUrl(returnTo));
  return { Authorization: `Bearer ${token}` };
}

/** GET for page data. A rejected session goes to the login page; other errors reach the error boundary. */
export async function memberGet<T>(path: string, returnTo = DASHBOARD_PATH): Promise<T> {
  const headers = await authHeaders(returnTo);
  try {
    return await api.get<T>(path, { headers, cache: "no-store" });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect(loginUrl(returnTo));
    throw error;
  }
}

export type MutationResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string; code?: string; fieldErrors: Record<string, string> };

const GENERIC_ERROR = "Something went wrong. Please try again.";

/** First message per field from a DRF validation error body. */
function fieldErrors(body: ApiErrorBody | null): Record<string, string> {
  const result: Record<string, string> = {};
  if (!body) return result;
  for (const [field, value] of Object.entries(body)) {
    if (field === "detail" || field === "code") continue;
    const message = Array.isArray(value) ? value[0] : value;
    if (typeof message === "string") result[field] = message;
  }
  return result;
}

/** POST/PATCH/DELETE for Server Actions. Never throws for API errors; returns a displayable failure. */
export async function memberMutate<T>(
  method: "post" | "patch" | "delete",
  path: string,
  body?: unknown,
  returnTo = DASHBOARD_PATH,
): Promise<MutationResult<T>> {
  // UI preview: nothing is ever sent to the API, and nothing claims to be saved.
  if (DASHBOARD_PREVIEW) return { ok: false, status: 0, message: PREVIEW_ACTION_MESSAGE, fieldErrors: {} };
  const headers = await authHeaders(returnTo);
  try {
    const options = { headers, cache: "no-store" as const };
    const data =
      method === "delete"
        ? await api.delete<T>(path, options)
        : await api[method]<T>(path, body ?? {}, options);
    return { ok: true, data };
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, status: 0, message: GENERIC_ERROR, fieldErrors: {} };
    if (error.status === 401) redirect(loginUrl(returnTo));
    if (error.isNetworkError) {
      return { ok: false, status: 0, message: "We couldn't reach our server. Please try again.", fieldErrors: {} };
    }
    const errors = fieldErrors(error.body);
    const detail = typeof error.body?.detail === "string" ? error.body.detail : undefined;
    return {
      ok: false,
      status: error.status,
      code: typeof error.body?.code === "string" ? error.body.code : undefined,
      message:
        detail ??
        (Object.keys(errors).length ? "Please correct the highlighted fields." : error.status === 429
          ? "Too many requests. Please wait a little and try again."
          : GENERIC_ERROR),
      fieldErrors: errors,
    };
  }
}

// --- Page data -------------------------------------------------------------
// In UI preview builds (preview.ts) every getter returns fictional sample data
// and the API is never called.

export const getDashboardSummary = async () =>
  DASHBOARD_PREVIEW ? previewSummary() : memberGet<DashboardSummary>("/dashboard/summary/");

/** The member's profile, or null if they haven't created one yet. */
export async function getOwnProfile(returnTo = DASHBOARD_PATH): Promise<OwnProfile | null> {
  if (DASHBOARD_PREVIEW) return previewProfile;
  try {
    return await memberGet<OwnProfile>("/profiles/me/", returnTo);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export const getOwnPhotos = async () =>
  DASHBOARD_PREVIEW ? previewPhotos : memberGet<OwnPhoto[]>("/profiles/me/photos/", "/dashboard/photos");

const pageQuery = (page: number, extra: Record<string, string> = {}) =>
  `?${new URLSearchParams({ page: String(page), ...extra })}`;

/** Lists need a profile; null means the member hasn't created one yet. */
async function listOrNull<T>(path: string, returnTo: string): Promise<Paginated<T> | null> {
  try {
    return await memberGet<Paginated<T>>(path, returnTo);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // A page past the end is also a 404 from the paginator; treat it as empty.
      return error.body?.code === "no_profile" ? null : { count: 0, next: null, previous: null, results: [] };
    }
    throw error;
  }
}

export const getReceivedInterests = async (page: number, status?: string) =>
  DASHBOARD_PREVIEW
    ? previewPage(previewReceived, page, status)
    : listOrNull<InterestItem>(`/interests/received/${pageQuery(page, status ? { status } : {})}`, "/dashboard/interests/received");

export const getSentInterests = async (page: number, status?: string) =>
  DASHBOARD_PREVIEW
    ? previewPage(previewSent, page, status)
    : listOrNull<InterestItem>(`/interests/sent/${pageQuery(page, status ? { status } : {})}`, "/dashboard/interests/sent");

export const getMatches = async (page: number) =>
  DASHBOARD_PREVIEW
    ? previewPage<MemberCard>(previewMatches, page)
    : listOrNull<MemberCard>(`/profiles/matches/${pageQuery(page)}`, "/dashboard/matches");

export const getShortlist = async (page: number) =>
  DASHBOARD_PREVIEW
    ? previewPage(previewShortlist, page)
    : listOrNull<ShortlistItem>(`/shortlist/${pageQuery(page)}`, "/dashboard/shortlisted");

export const getMembership = async () =>
  DASHBOARD_PREVIEW ? previewMembership : memberGet<MembershipInfo>("/memberships/me/", "/dashboard/membership");

export const getNotifications = async (page: number) =>
  DASHBOARD_PREVIEW
    ? {
        ...previewPage(previewNotifications, page),
        unread_count: previewNotifications.filter((item) => !item.read).length,
      }
    : memberGet<Paginated<NotificationItem> & { unread_count: number }>(
        `/notifications/${pageQuery(page)}`,
        "/dashboard/notifications",
      );

export interface AccountInfo {
  id: string;
  email: string;
  phone_number: string | null;
  first_name: string;
  last_name: string;
  email_verified_at: string | null;
  phone_verified_at: string | null;
  date_joined: string;
}

export const getAccount = async () =>
  DASHBOARD_PREVIEW ? previewAccount : memberGet<AccountInfo>("/auth/me/", "/dashboard/settings");
