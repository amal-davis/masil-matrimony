"use server";

import type { CountryCode } from "libphonenumber-js";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { quickRegistrationSchema, type QuickRegistrationInput } from "@/features/registration/schema";
import { api, ApiError } from "@/lib/api/client";

import {
  clearChallenge,
  delayResend,
  pendingView,
  readChallenge,
  storeChallenge,
  type ChallengePurpose,
  type CodeIssued,
  type PendingCode,
} from "./challenge";
import { AFTER_REGISTER, VERIFY_MOBILE_PATH } from "./constants";
import { safeRedirectPath } from "./redirect";
import {
  changeMobileSchema,
  loginPhoneSchema,
  OTP_PATTERN,
  toMobileE164,
  type ChangeMobileInput,
  type LoginPhoneInput,
} from "./schema";
import { endSession, startSession, type TokenPair } from "./session";

/**
 * SMS-code sign-in and registration, run on the Next.js server
 * (docs/architecture.md, "Web browser strategy"): the browser never talks to
 * the token endpoints or sees a token or challenge id. Server Actions check the
 * request Origin, so these can't be called cross-site. Inputs are validated
 * again here and by the API; the forms' checks are only for convenience.
 */

export type { PendingCode };

/** A code was sent (`pending` is the code screen), or why not. */
export type SendCodeResult =
  | { ok: true; pending: PendingCode }
  | {
      ok: false;
      message: string;
      /** The number field is what's wrong. */
      field?: "phone";
      /** Seconds before another code may be requested. */
      retryAfter?: number;
      /** The registration (or sign-in) on this browser has expired: start again. */
      expired?: boolean;
      /** The number already has an account: offer to log in. */
      phoneRegistered?: boolean;
    };

/** Why a code was rejected. All but "incorrect" and "error" mean this code can't be used again. */
export type VerifyFailure = "incorrect" | "expired" | "used" | "attempts" | "invalid" | "conflict" | "error";

/** On success the verify actions redirect, so they only return failures. */
export type VerifyCodeResult = { ok: false; reason: VerifyFailure; message: string; attemptsRemaining?: number };

export type RegisterField =
  | "createdFor"
  | "gender"
  | "fullName"
  | "dateOfBirth"
  | "country"
  | "mobile"
  | "email"
  | "acceptTerms";

export type RegisterResult = {
  ok: false;
  message?: string;
  fieldErrors?: Partial<Record<RegisterField, string>>;
  phoneRegistered?: boolean;
};

const GENERIC_ERROR = "Something went wrong. Please try again.";
const NETWORK_ERROR = "We couldn't reach our server. Please check your connection and try again.";
const DEVICE_LIMIT = "Too many attempts from this device. Please wait a while and try again.";
const SMS_UNAVAILABLE = "We can't send SMS codes right now. Please try again later, or contact us.";
const SMS_FAILED = "We couldn't send the SMS just now. Please try again in a few minutes.";
const PHONE_REGISTERED = "An account already uses this mobile number. Please log in instead.";

/** Pass the visitor's address on so the API's per-IP limits apply to them, not to this server. */
async function forwardingHeaders(): Promise<HeadersInit> {
  const incoming = await headers();
  const forwardedFor = incoming.get("x-forwarded-for") ?? incoming.get("x-real-ip");
  return forwardedFor ? { "X-Forwarded-For": forwardedFor } : {};
}

function errorCode(error: ApiError): string | undefined {
  return typeof error.body?.code === "string" ? error.body.code : undefined;
}

function retryAfter(error: ApiError): number | undefined {
  const value = error.body?.retry_after;
  return typeof value === "number" && value > 0 ? value : undefined;
}

/** Field errors from a DRF 400 response, joined into one sentence. */
function fieldMessage(error: ApiError, field: string): string | undefined {
  const value = (error.body as Record<string, unknown> | null)?.[field];
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value.join(" ") : undefined;
}

const post = async <T>(path: string, body: unknown) =>
  api.post<T>(path, body, { headers: await forwardingHeaders(), cache: "no-store" });

/** Sign out whoever this browser was signed in as, so a new session never reuses an old one. */
async function retirePreviousSession() {
  const previous = await endSession();
  if (previous) {
    await api.post("/auth/token/blacklist/", { refresh: previous }, { cache: "no-store" }).catch(() => undefined);
  }
}

/** A failed request for a code, as the code screen or number form should show it. */
function sendFailure(error: unknown): Extract<SendCodeResult, { ok: false }> {
  if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
  if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
  switch (error.status) {
    case 400:
      return { ok: false, field: "phone", message: fieldMessage(error, "phone_number") ?? "Check the mobile number and try again." };
    case 409:
      return { ok: false, field: "phone", phoneRegistered: true, message: PHONE_REGISTERED };
    case 410:
      return { ok: false, expired: true, message: "Your registration has expired. Please fill in the form again." };
    case 429: {
      if (errorCode(error) !== "otp_rate_limited") return { ok: false, message: DEVICE_LIMIT };
      const wait = retryAfter(error);
      return {
        ok: false,
        retryAfter: wait,
        message:
          wait && wait > 120
            ? `You've requested several codes for this number. Please try again in about ${Math.ceil(wait / 60)} minutes.`
            : `A code was sent to this number recently. Please wait ${wait ?? 60} seconds before requesting another.`,
      };
    }
    case 503:
      return { ok: false, message: errorCode(error) === "otp_delivery_failed" ? SMS_FAILED : SMS_UNAVAILABLE };
    default:
      return { ok: false, message: GENERIC_ERROR };
  }
}

const VERIFY_FAILURES: Record<string, { reason: VerifyFailure; message: string }> = {
  otp_incorrect: { reason: "incorrect", message: "That code is incorrect. Please check the SMS and try again." },
  otp_expired: { reason: "expired", message: "This code has expired. Please request a new one." },
  otp_used: { reason: "used", message: "This code has already been used. Please request a new one." },
  otp_attempts_exceeded: { reason: "attempts", message: "Too many incorrect attempts. Please request a new code." },
  otp_invalid: { reason: "invalid", message: "This code is no longer valid. Please request a new one." },
  phone_registered: { reason: "conflict", message: PHONE_REGISTERED },
  email_taken: {
    reason: "conflict",
    message: "Another account started using your email address meanwhile. Please register again with a different email, or leave it empty.",
  },
};

function verifyFailure(error: unknown): VerifyCodeResult {
  if (!(error instanceof ApiError)) return { ok: false, reason: "error", message: GENERIC_ERROR };
  if (error.isNetworkError) return { ok: false, reason: "error", message: NETWORK_ERROR };
  if (error.status === 429) return { ok: false, reason: "error", message: DEVICE_LIMIT };
  const failure = VERIFY_FAILURES[errorCode(error) ?? ""];
  if ((error.status === 400 || error.status === 409) && failure) {
    const remaining = error.body?.attempts_remaining;
    return { ok: false, ...failure, attemptsRemaining: typeof remaining === "number" ? remaining : undefined };
  }
  if (error.status === 400) return { ok: false, reason: "incorrect", message: "Enter the complete code from the SMS." };
  return { ok: false, reason: "error", message: GENERIC_ERROR };
}

const NO_PENDING: Record<ChallengePurpose, VerifyCodeResult> = {
  login: { ok: false, reason: "invalid", message: "This code has expired on this device. Please enter your mobile number again." },
  register: {
    ok: false,
    reason: "invalid",
    message: "Your registration has expired on this device. Please fill in the registration form again.",
  },
};

function checkCode(code: unknown): code is string {
  return typeof code === "string" && OTP_PATTERN.test(code);
}

// --- Sign-in -----------------------------------------------------------------

/** Send a sign-in code. The API answers the same whether or not the number is registered. */
export async function requestLoginCode(values: LoginPhoneInput): Promise<SendCodeResult> {
  const parsed = loginPhoneSchema.safeParse(values);
  if (!parsed.success) {
    return { ok: false, field: "phone", message: parsed.error.issues[0]?.message ?? "Enter your mobile number." };
  }
  try {
    const issued = await post<CodeIssued>("/auth/otp/request/", { phone_number: parsed.data.phoneNumber });
    await storeChallenge("login", issued, parsed.data.remember);
    const stored = await readChallenge("login");
    return stored ? { ok: true, pending: pendingView(stored) } : { ok: false, message: GENERIC_ERROR };
  } catch (error) {
    return sendFailure(error);
  }
}

/** Send a new sign-in code to the number on the code screen. */
export async function resendLoginCode(): Promise<SendCodeResult> {
  const stored = await readChallenge("login");
  if (!stored) return { ok: false, expired: true, message: "Please enter your mobile number again." };
  try {
    const issued = await post<CodeIssued>("/auth/otp/request/", { phone_number: stored.phoneNumber });
    await storeChallenge("login", issued, stored.remember);
    const updated = await readChallenge("login");
    return updated ? { ok: true, pending: pendingView(updated) } : { ok: false, message: GENERIC_ERROR };
  } catch (error) {
    const failure = sendFailure(error);
    if (failure.retryAfter) await delayResend("login", failure.retryAfter);
    return failure;
  }
}

/**
 * Check the sign-in code. On success this stores the session cookies and
 * redirects (to `next` when it is a safe path on this site), so it only returns failures.
 */
export async function verifyLoginCode(code: string, next?: string): Promise<VerifyCodeResult> {
  if (!checkCode(code)) return { ok: false, reason: "incorrect", message: "Enter the complete code from the SMS." };
  const stored = await readChallenge("login");
  if (!stored) return NO_PENDING.login;

  let tokens: TokenPair;
  try {
    tokens = await post<TokenPair>("/auth/otp/verify/", { challenge_id: stored.id, code });
  } catch (error) {
    return verifyFailure(error);
  }
  await retirePreviousSession();
  await startSession(tokens, { remember: stored.remember });
  await clearChallenge();
  redirect(safeRedirectPath(next));
}

/** Forget the code this browser is waiting for ("Change mobile number" on the sign-in screen). */
export async function cancelPendingCode(): Promise<void> {
  await clearChallenge();
}

// --- Registration --------------------------------------------------------------

/** API field names → registration form fields. */
const REGISTER_FIELDS: Record<string, RegisterField> = {
  created_for: "createdFor",
  gender: "gender",
  display_name: "fullName",
  date_of_birth: "dateOfBirth",
  phone_number: "mobile",
  email: "email",
  accept_terms: "acceptTerms",
};

/**
 * Check the details and send a code by SMS to the mobile number. No account
 * exists until that code is entered: on success this redirects to the code
 * screen (VERIFY_MOBILE_PATH), so it only returns failures.
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

  let issued: CodeIssued;
  try {
    issued = await post<CodeIssued>("/auth/register/", {
      phone_number: toMobileE164(data.mobile, data.country as CountryCode),
      email: data.email,
      accept_terms: data.acceptTerms,
      created_for: data.createdFor,
      display_name: data.fullName,
      gender: data.gender,
      date_of_birth: data.dateOfBirth,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) {
      const fieldErrors: Partial<Record<RegisterField, string>> = {};
      for (const [apiField, formField] of Object.entries(REGISTER_FIELDS)) {
        const message = fieldMessage(error, apiField);
        if (message) fieldErrors[formField] = message;
      }
      return Object.keys(fieldErrors).length
        ? { ok: false, fieldErrors }
        : { ok: false, message: "Please check your details and try again." };
    }
    const failure = sendFailure(error);
    if (failure.phoneRegistered) {
      return { ok: false, phoneRegistered: true, fieldErrors: { mobile: PHONE_REGISTERED } };
    }
    return { ok: false, message: failure.message };
  }

  await storeChallenge("register", issued);
  redirect(VERIFY_MOBILE_PATH);
}

/**
 * Send a new registration code, to the same number or (with `change`) a
 * corrected one, without filling in the form again.
 */
export async function resendRegistrationCode(change?: ChangeMobileInput): Promise<SendCodeResult> {
  const stored = await readChallenge("register");
  if (!stored) {
    return { ok: false, expired: true, message: "Your registration has expired on this device. Please fill in the form again." };
  }
  let phoneNumber: string | undefined;
  if (change) {
    const parsed = changeMobileSchema.safeParse(change);
    if (!parsed.success) {
      return { ok: false, field: "phone", message: parsed.error.issues[0]?.message ?? "Enter your mobile number." };
    }
    phoneNumber = parsed.data.phoneNumber;
  }

  try {
    const issued = await post<CodeIssued>("/auth/register/resend/", {
      challenge_id: stored.id,
      ...(phoneNumber ? { phone_number: phoneNumber } : {}),
    });
    await storeChallenge("register", issued);
    const updated = await readChallenge("register");
    return updated ? { ok: true, pending: pendingView(updated) } : { ok: false, message: GENERIC_ERROR };
  } catch (error) {
    const failure = sendFailure(error);
    if (failure.expired) await clearChallenge();
    if (failure.retryAfter && !phoneNumber) await delayResend("register", failure.retryAfter);
    return failure;
  }
}

/**
 * Check the registration code. On success the API creates the account and
 * profile; this stores the session and opens the new member's profile, so it
 * only returns failures.
 */
export async function verifyRegistrationCode(code: string): Promise<VerifyCodeResult> {
  if (!checkCode(code)) return { ok: false, reason: "incorrect", message: "Enter the complete code from the SMS." };
  const stored = await readChallenge("register");
  if (!stored) return NO_PENDING.register;

  let tokens: TokenPair;
  try {
    tokens = await post<TokenPair>("/auth/register/verify/", { challenge_id: stored.id, code });
  } catch (error) {
    const failure = verifyFailure(error);
    // The registration can't be completed with these details: start again.
    if (failure.reason === "conflict") await clearChallenge();
    return failure;
  }
  await retirePreviousSession();
  await startSession(tokens, { remember: false });
  await clearChallenge();
  redirect(AFTER_REGISTER);
}
