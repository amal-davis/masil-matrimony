"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import { quickRegistrationSchema, type QuickRegistrationInput } from "@/features/registration/schema";
import { api, ApiError } from "@/lib/api/client";

import { REFRESH_COOKIE } from "./constants";
import { safeRedirectPath } from "./redirect";
import { forgotPasswordSchema, loginSchema, resetPasswordSchema, type LoginValues } from "./schema";
import { endSession, startSession, type TokenPair } from "./session";

/**
 * Email + password sign-in and password reset, run on the Next.js server
 * (docs/architecture.md, "Web browser strategy"): the browser never talks to
 * the token endpoints or sees a token. Server Actions check the request
 * Origin, so these can't be called cross-site. Inputs are validated again
 * here and by the API; the form's checks are only for convenience.
 */

export type SignInResult = { ok: false; message: string };

export type RegisterField =
  | "createdFor"
  | "gender"
  | "fullName"
  | "dateOfBirth"
  | "mobile"
  | "email"
  | "password"
  | "acceptTerms";

export type RegisterResult = { ok: false; message?: string; fieldErrors?: Partial<Record<RegisterField, string>> };

export type ForgotPasswordResult = { ok: true } | { ok: false; message: string };

export type ResetPasswordResult =
  | { ok: true }
  | { ok: false; reason: "link" | "error"; message: string }
  | { ok: false; reason: "password"; message: string; field: "password" | "confirm" };

const GENERIC_ERROR = "Something went wrong. Please try again.";
const NETWORK_ERROR = "We couldn't reach our server. Please check your connection and try again.";
const DEVICE_LIMIT = "Too many attempts from this device. Please wait a while and try again.";
const INVALID_CREDENTIALS = "The email address or password is incorrect.";
const LINK_INVALID = "This password reset link is invalid or has expired. Please request a new one.";

/** Pass the visitor's address on so the API's per-IP limits apply to them, not to this server. */
async function forwardingHeaders(): Promise<HeadersInit> {
  const incoming = await headers();
  const forwardedFor = incoming.get("x-forwarded-for") ?? incoming.get("x-real-ip");
  return forwardedFor ? { "X-Forwarded-For": forwardedFor } : {};
}

function errorCode(error: ApiError): string | undefined {
  return typeof error.body?.code === "string" ? error.body.code : undefined;
}

function waitMessage(error: ApiError): string {
  const seconds = error.body?.retry_after;
  if (typeof seconds !== "number" || seconds <= 0) return "later";
  const minutes = Math.ceil(seconds / 60);
  return minutes <= 1 ? "in a minute" : `in about ${minutes} minutes`;
}

/** Field errors from a DRF 400 response, joined into one sentence. */
function fieldMessage(error: ApiError, field: string): string | undefined {
  const value = (error.body as Record<string, unknown> | null)?.[field];
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value.join(" ") : undefined;
}

/**
 * Check the email and password. On success this stores the session cookies and
 * redirects (to `next` when it is a safe path on this site), so it only returns failures.
 */
export async function signIn(values: LoginValues, next?: string): Promise<SignInResult> {
  const parsed = loginSchema.safeParse(values);
  if (!parsed.success) return { ok: false, message: "Enter your email address and password." };
  const { email, password, remember } = parsed.data;

  let tokens: TokenPair;
  try {
    tokens = await api.post<TokenPair>(
      "/auth/login/",
      { email, password },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    switch (error.status) {
      case 400:
        return { ok: false, message: INVALID_CREDENTIALS };
      case 429:
        return errorCode(error) === "login_rate_limited"
          ? {
              ok: false,
              message: `Too many unsuccessful attempts for this email address. Please try again ${waitMessage(error)}, or reset your password.`,
            }
          : { ok: false, message: DEVICE_LIMIT };
      default:
        return { ok: false, message: GENERIC_ERROR };
    }
  }

  // A new session never reuses an old one: retire any refresh token this browser still holds.
  const previous = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (previous) {
    await api.post("/auth/token/blacklist/", { refresh: previous }, { cache: "no-store" }).catch(() => undefined);
  }
  await startSession(tokens, { remember });
  redirect(safeRedirectPath(next));
}

/** API field names → registration form fields. */
const REGISTER_FIELDS: Record<string, RegisterField> = {
  created_for: "createdFor",
  gender: "gender",
  display_name: "fullName",
  date_of_birth: "dateOfBirth",
  phone_number: "mobile",
  email: "email",
  password: "password",
  accept_terms: "acceptTerms",
};

/** The page new members land on: their profile, to finish it. */
const AFTER_REGISTER = "/dashboard/my-profile";

/**
 * Create the account and draft profile, then sign the new member in and
 * redirect to their profile. Only returns failures.
 */
export async function registerMember(values: QuickRegistrationInput): Promise<RegisterResult> {
  const parsed = quickRegistrationSchema.safeParse(values);
  if (!parsed.success) {
    const fieldErrors: Partial<Record<RegisterField, string>> = {};
    for (const issue of parsed.error.issues) {
      const field = issue.path[0] as RegisterField;
      fieldErrors[field] ??= issue.message;
    }
    return { ok: false, fieldErrors };
  }
  const data = parsed.data;

  let tokens: TokenPair;
  try {
    tokens = await api.post<TokenPair>(
      "/auth/register/",
      {
        email: data.email,
        password: data.password,
        phone_number: `+91${data.mobile}`,
        accept_terms: data.acceptTerms,
        created_for: data.createdFor,
        display_name: data.fullName,
        gender: data.gender,
        date_of_birth: data.dateOfBirth,
      },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    if (error.status === 429) return { ok: false, message: DEVICE_LIMIT };
    if (error.status !== 400) return { ok: false, message: GENERIC_ERROR };

    const fieldErrors: Partial<Record<RegisterField, string>> = {};
    for (const [apiField, formField] of Object.entries(REGISTER_FIELDS)) {
      const message = fieldMessage(error, apiField);
      if (message) fieldErrors[formField] = message;
    }
    return Object.keys(fieldErrors).length
      ? { ok: false, fieldErrors }
      : { ok: false, message: "Please check your details and try again." };
  }

  const previous = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (previous) {
    await api.post("/auth/token/blacklist/", { refresh: previous }, { cache: "no-store" }).catch(() => undefined);
  }
  await startSession(tokens, { remember: false });
  redirect(AFTER_REGISTER);
}

/** Ask the API to email a reset link. Succeeds the same way whether or not the address is registered. */
export async function requestPasswordReset(email: string): Promise<ForgotPasswordResult> {
  const parsed = forgotPasswordSchema.safeParse({ email });
  if (!parsed.success) return { ok: false, message: "Enter a valid email address, e.g. name@example.com." };

  try {
    await api.post(
      "/auth/password/reset/",
      { email: parsed.data.email },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
    return { ok: true };
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    switch (error.status) {
      case 400:
        return { ok: false, message: "Enter a valid email address, e.g. name@example.com." };
      case 429:
        return errorCode(error) === "password_reset_rate_limited"
          ? {
              ok: false,
              message: `You've requested several reset links for this address. Please check your inbox (and spam folder), or try again ${waitMessage(error)}.`,
            }
          : { ok: false, message: DEVICE_LIMIT };
      case 503:
        // Email isn't configured on the server: say so rather than pretend a link was sent.
        return {
          ok: false,
          message: "Password reset by email isn't available right now. Please contact us and we'll help you sign in.",
        };
      default:
        return { ok: false, message: GENERIC_ERROR };
    }
  }
}

/** Set a new password from an emailed link. Signs this browser out too, as the API does for every device. */
export async function resetPassword(
  uid: string,
  token: string,
  password: string,
  confirm: string,
): Promise<ResetPasswordResult> {
  if (typeof uid !== "string" || typeof token !== "string" || !uid || !token || uid.length > 64 || token.length > 64) {
    return { ok: false, reason: "link", message: LINK_INVALID };
  }
  const parsed = resetPasswordSchema.safeParse({ password, confirm });
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    return { ok: false, reason: "password", field: issue.path[0] === "confirm" ? "confirm" : "password", message: issue.message };
  }

  try {
    await api.post(
      "/auth/password/reset/confirm/",
      { uid, token, new_password: parsed.data.password, new_password_confirm: parsed.data.confirm },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, reason: "error", message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, reason: "error", message: NETWORK_ERROR };
    if (error.status === 429) return { ok: false, reason: "error", message: DEVICE_LIMIT };
    if (error.status !== 400) return { ok: false, reason: "error", message: GENERIC_ERROR };

    const passwordError = fieldMessage(error, "new_password");
    if (passwordError) return { ok: false, reason: "password", field: "password", message: passwordError };
    const confirmError = fieldMessage(error, "new_password_confirm");
    if (confirmError) return { ok: false, reason: "password", field: "confirm", message: confirmError };
    // reset_link_invalid, or a malformed uid/token in the link.
    return { ok: false, reason: "link", message: LINK_INVALID };
  }

  await endSession();
  return { ok: true };
}
