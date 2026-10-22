"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/api/client";

import { safeRedirectPath } from "./redirect";
import { INDIA_MOBILE_E164 } from "./schema";
import { startSession, type TokenPair } from "./session";

/**
 * SMS login, run on the Next.js server (docs/architecture.md, "Web browser
 * strategy"): the browser never talks to the token endpoints or sees a token.
 * Server Actions check the request Origin, so these can't be called cross-site.
 */

export type RequestCodeResult =
  | { ok: true; challengeId: string; codeLength: number; expiresIn: number; resendAfter: number }
  | { ok: false; message: string; field?: "phone"; retryAfter?: number };

/** Why a code was rejected. All but "incorrect" mean the code can't be used again. */
export type VerifyFailure = "incorrect" | "expired" | "used" | "attempts" | "invalid" | "error";

export type VerifyCodeResult = { ok: false; reason: VerifyFailure; message: string; attemptsRemaining?: number };

interface OtpRequested {
  challenge_id: string;
  code_length: number;
  expires_in: number;
  resend_after: number;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const GENERIC_ERROR = "Something went wrong. Please try again.";
const NETWORK_ERROR = "We couldn't reach our server. Please check your connection and try again.";
const INVALID_NUMBER = "Enter a valid 10-digit Indian mobile number, e.g. 98765 43210.";

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

export async function requestLoginCode(phoneNumber: string): Promise<RequestCodeResult> {
  if (typeof phoneNumber !== "string" || !INDIA_MOBILE_E164.test(phoneNumber)) {
    return { ok: false, field: "phone", message: INVALID_NUMBER };
  }

  try {
    const data = await api.post<OtpRequested>(
      "/auth/otp/request/",
      { phone_number: phoneNumber },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
    return {
      ok: true,
      challengeId: data.challenge_id,
      codeLength: data.code_length,
      expiresIn: data.expires_in,
      resendAfter: data.resend_after,
    };
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, message: NETWORK_ERROR };
    switch (error.status) {
      case 400:
        return { ok: false, field: "phone", message: INVALID_NUMBER };
      case 429:
        if (errorCode(error) === "otp_rate_limited") {
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
        return { ok: false, message: "Too many attempts from this device. Please try again later." };
      case 503:
        return errorCode(error) === "otp_delivery_failed"
          ? { ok: false, message: "We couldn't send the code right now. Please try again in a few minutes." }
          : { ok: false, message: "Login by SMS is not available right now. Please try again later." };
      default:
        return { ok: false, message: GENERIC_ERROR };
    }
  }
}

const VERIFY_FAILURES: Record<string, { reason: VerifyFailure; message: string }> = {
  otp_incorrect: { reason: "incorrect", message: "That code is incorrect. Please check the SMS and try again." },
  otp_expired: { reason: "expired", message: "This code has expired. Please request a new one." },
  otp_used: { reason: "used", message: "This code has already been used. Please request a new one." },
  otp_attempts_exceeded: {
    reason: "attempts",
    message: "Too many incorrect attempts. Please request a new code.",
  },
  otp_invalid: { reason: "invalid", message: "This code is no longer valid. Please request a new one." },
};

/**
 * Check the code. On success this stores the session cookies and redirects
 * (to `next` when it is a safe path on this site), so it only returns failures.
 */
export async function verifyLoginCode(challengeId: string, code: string, next?: string): Promise<VerifyCodeResult> {
  if (typeof challengeId !== "string" || !UUID_PATTERN.test(challengeId)) {
    return { ok: false, ...VERIFY_FAILURES.otp_invalid };
  }
  if (typeof code !== "string" || !/^\d{4,10}$/.test(code)) {
    return { ok: false, reason: "incorrect", message: "Enter the complete code from the SMS." };
  }

  let tokens: TokenPair;
  try {
    tokens = await api.post<TokenPair>(
      "/auth/otp/verify/",
      { challenge_id: challengeId, code },
      { headers: await forwardingHeaders(), cache: "no-store" },
    );
  } catch (error) {
    if (!(error instanceof ApiError)) return { ok: false, reason: "error", message: GENERIC_ERROR };
    if (error.isNetworkError) return { ok: false, reason: "error", message: NETWORK_ERROR };
    if (error.status === 429) {
      return { ok: false, reason: "error", message: "Too many attempts from this device. Please try again later." };
    }
    const failure = VERIFY_FAILURES[errorCode(error) ?? ""];
    if (error.status === 400 && failure) {
      const remaining = error.body?.attempts_remaining;
      return {
        ok: false,
        ...failure,
        attemptsRemaining: typeof remaining === "number" ? remaining : undefined,
      };
    }
    if (error.status === 400) return { ok: false, reason: "incorrect", message: "Enter the complete code from the SMS." };
    return { ok: false, reason: "error", message: GENERIC_ERROR };
  }

  await startSession(tokens);
  redirect(safeRedirectPath(next));
}
