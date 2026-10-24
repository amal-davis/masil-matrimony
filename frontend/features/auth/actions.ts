"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import { quickRegistrationSchema, type QuickRegistrationInput } from "@/features/registration/schema";
import { api, ApiError } from "@/lib/api/client";

import { CHECK_EMAIL_PATH, PENDING_EMAIL_COOKIE, REFRESH_COOKIE } from "./constants";
import { safeRedirectPath } from "./redirect";
import { forgotPasswordSchema, loginSchema, resetPasswordSchema, type LoginValues } from "./schema";
import { endSession, pendingEmail, startSession, type TokenPair } from "./session";
import { baseCookie } from "./tokens";

/**
 * Email + password sign-in and password reset, run on the Next.js server
 * (docs/architecture.md, "Web browser strategy"): the browser never talks to
 * the token endpoints or sees a token. Server Actions check the request
 * Origin, so these can't be called cross-site. Inputs are validated again
 * here and by the API; the form's checks are only for convenience.
 */

/** `unverified`: right password, but the email address hasn't been verified yet. */
export type SignInResult = { ok: false; message: string; unverified?: boolean };

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

export type ResendVerificationResult =
  | { ok: true; message: string; consoleOnly: boolean }
  | { ok: false; message: string; needsEmail?: boolean };

export type ChangeEmailResult =
  | { ok: true; email: string; consoleOnly: boolean }
  | { ok: false; message: string; field?: "password" | "newEmail" };

export type VerifyEmailResult =
  /** `signedIn`: the session cookies are set, so the member can go straight to the dashboard. */
  | { ok: true; message: string; signedIn: boolean }
  | { ok: false; reason: "expired" | "invalid" | "used" | "error"; message: string };

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
      case 403:
        if (errorCode(error) === "email_not_verified") {
          // The password was right: remember the address so a new link can be sent without retyping it.
          await rememberPendingEmail(email);
          return {
            ok: false,
            unverified: true,
            message: "Please verify your email address before signing in. Open the link we emailed you, or send a new one.",
          };
        }
        return { ok: false, message: GENERIC_ERROR };
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

/** What the API answers to a registration (also to an already-registered address). */
type RegistrationResponse = {
  detail: string;
  email: string;
  email_sent: boolean;
  /** Why no email went out: "failed" or "rate_limited". */
  not_sent_reason?: string;
  delivery?: string;
};

/** The API's development console backend prints emails instead of sending them. */
const CONSOLE_NOTE =
  " (Development: the email was printed in the Django server's terminal, not delivered. Copy the link from there.)";

/**
 * Create the account and draft profile. The account starts unverified, so no
 * session is started: this redirects to the "Check your email" page (saying so
 * honestly if the email couldn't be sent) and only returns failures.
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

  let result: RegistrationResponse;
  try {
    result = await api.post<RegistrationResponse>(
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
    if (error.status === 503) {
      return {
        ok: false,
        message:
          "We can't send verification emails right now, so we can't create new accounts. Please try again later, or contact us.",
      };
    }
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

  // Whoever was signed in on this browser before is signed out: the new account isn't usable yet.
  const previous = await endSession();
  if (previous) {
    await api.post("/auth/token/blacklist/", { refresh: previous }, { cache: "no-store" }).catch(() => undefined);
  }
  await rememberPendingEmail(result.email);
  const query = new URLSearchParams();
  // Only the send status and delivery mode go in the URL, never the address.
  if (!result.email_sent) query.set("status", result.not_sent_reason === "rate_limited" ? "rate-limited" : "not-sent");
  if (result.delivery === "console") query.set("delivery", "console");
  redirect(query.size ? `${CHECK_EMAIL_PATH}?${query}` : CHECK_EMAIL_PATH);
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

// --- Email verification ------------------------------------------------------

const PENDING_EMAIL_MAX_AGE = 60 * 60 * 24; // a day, like the link itself

async function rememberPendingEmail(email: string) {
  (await cookies()).set(PENDING_EMAIL_COOKIE, email, { ...baseCookie, maxAge: PENDING_EMAIL_MAX_AGE });
}

/**
 * Send a new verification link to the address waiting on this browser, or to
 * `email` when given (e.g. after the cookie expired). The API answers the same
 * way whether or not the address has an unverified account.
 */
export async function resendVerification(email?: string): Promise<ResendVerificationResult> {
  const address = email ?? (await pendingEmail());
  if (!address) return { ok: false, needsEmail: true, message: "Enter the email address you registered with." };
  if (!forgotPasswordSchema.safeParse({ email: address }).success) {
    return { ok: false, needsEmail: true, message: "Enter a valid email address, e.g. name@example.com." };
  }

  let delivery: string | undefined;
  try {
    ({ delivery } = await api.post<{ delivery?: string }>(
      "/auth/email/resend/",
      { email: address },
      { headers: await forwardingHeaders(), cache: "no-store" },
    ));
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    switch (error.status) {
      case 429:
        return errorCode(error) === "verification_rate_limited"
          ? {
              ok: false,
              message: `We've sent several verification emails to this address. Please check your inbox and spam folder, or try again ${waitMessage(error)}.`,
            }
          : { ok: false, message: DEVICE_LIMIT };
      case 503:
        // Say so honestly rather than pretend a link was sent.
        return { ok: false, message: "We couldn't send the email just now. Please try again in a few minutes." };
      default:
        return { ok: false, message: GENERIC_ERROR };
    }
  }
  if (email) await rememberPendingEmail(address);
  const consoleOnly = delivery === "console";
  return {
    ok: true,
    consoleOnly,
    message:
      `If ${address} has an account waiting for verification, we've sent it a new link. Only the newest link works.` +
      (consoleOnly ? CONSOLE_NOTE : ""),
  };
}

/**
 * Correct a mistyped address before it is verified. Needs the account's
 * password (checked by the API), so nobody can move an account to their own address.
 */
export async function changeUnverifiedEmail(password: string, newEmail: string): Promise<ChangeEmailResult> {
  const current = await pendingEmail();
  if (!current) return { ok: false, message: "Your registration details have expired on this device. Please sign in instead." };
  if (!forgotPasswordSchema.safeParse({ email: newEmail }).success) {
    return { ok: false, field: "newEmail", message: "Enter a valid email address, e.g. name@example.com." };
  }
  if (!password) return { ok: false, field: "password", message: "Enter the password you chose when registering." };

  let result: RegistrationResponse;
  try {
    result = await api.post<RegistrationResponse>(
      "/auth/email/change/",
      { email: current, password, new_email: newEmail.trim() },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    switch (errorCode(error)) {
      case "invalid_credentials":
        return { ok: false, field: "password", message: "That password isn't right for this registration." };
      case "email_taken":
        return { ok: false, field: "newEmail", message: "Another account already uses this email address." };
      case "email_change_not_allowed":
        return { ok: false, message: "This address is already verified. Please sign in." };
      case "login_rate_limited":
        return { ok: false, message: `Too many unsuccessful attempts. Please try again ${waitMessage(error)}.` };
      case "verification_rate_limited":
        return { ok: false, message: `We've sent several emails recently. Please try again ${waitMessage(error)}.` };
      case "verification_email_failed":
        return { ok: false, message: "We couldn't send the email just now. Please try again in a few minutes." };
      default:
        return { ok: false, message: error.status === 429 ? DEVICE_LIMIT : GENERIC_ERROR };
    }
  }
  await rememberPendingEmail(result.email);
  return { ok: true, email: result.email, consoleOnly: result.delivery === "console" };
}

/**
 * Check a verification link's token with the API. When the link verifies the
 * account, the API also returns a session (only that once), stored here like a
 * normal sign-in, so the member goes straight to the dashboard. The browser
 * never sees the tokens; "Keep me signed in" stays off.
 */
export async function verifyEmail(token: string): Promise<VerifyEmailResult> {
  if (typeof token !== "string" || token.length === 0 || token.length > 512) {
    return { ok: false, reason: "invalid", message: "This verification link is incomplete or invalid." };
  }
  try {
    const result = await api.post<{ detail: string } & Partial<TokenPair>>(
      "/auth/email/verify/",
      { token },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
    (await cookies()).delete(PENDING_EMAIL_COOKIE);
    if (!result.access || !result.refresh) return { ok: true, message: result.detail, signedIn: false };

    // A new session never reuses an old one: retire whatever this browser was signed in as.
    const previous = await endSession();
    if (previous) {
      await api.post("/auth/token/blacklist/", { refresh: previous }, { cache: "no-store" }).catch(() => undefined);
    }
    await startSession({ access: result.access, refresh: result.refresh }, { remember: false });
    return { ok: true, message: result.detail, signedIn: true };
  } catch (error) {
    if (!(error instanceof ApiError) || error.isNetworkError || error.status >= 500 || error.status === 429) {
      return {
        ok: false,
        reason: "error",
        message:
          error instanceof ApiError && error.status === 429
            ? DEVICE_LIMIT
            : "We couldn't check your link just now. Please check your connection and try again.",
      };
    }
    switch (errorCode(error)) {
      case "verification_link_expired":
        return { ok: false, reason: "expired", message: "This verification link has expired. Links work for 24 hours." };
      case "email_already_verified":
        (await cookies()).delete(PENDING_EMAIL_COOKIE);
        return { ok: false, reason: "used", message: "This email address has already been verified. You can sign in." };
      default:
        return {
          ok: false,
          reason: "invalid",
          message:
            "This verification link is invalid, or a newer link has replaced it. Please use the latest email we sent, or request a new link.",
        };
    }
  }
}
