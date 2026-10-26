import { cookies } from "next/headers";

import { OTP_CHALLENGE_COOKIE } from "./constants";
import { maskPhoneNumber } from "./schema";
import { baseCookie } from "./tokens";

/**
 * The SMS code this browser is waiting for, kept in an HTTP-only cookie
 * (OTP_CHALLENGE_COOKIE) by the Server Actions, so the code screen survives a
 * refresh and the challenge id never reaches browser JavaScript. Server-only.
 */

export type ChallengePurpose = "login" | "register";

/** What the code screen shows. The challenge id is not part of it. */
export interface PendingCode {
  purpose: ChallengePurpose;
  /** E.164; the member's own number, to prefill "Change mobile number". */
  phoneNumber: string;
  maskedPhone: string;
  codeLength: number;
  /** Epoch milliseconds. */
  expiresAt: number;
  resendAt: number;
}

interface StoredChallenge {
  purpose: ChallengePurpose;
  id: string;
  phoneNumber: string;
  codeLength: number;
  expiresAt: number;
  resendAt: number;
  /** Sign-in only: "Keep me signed in". */
  remember: boolean;
}

/** The API's answer when it sends a code. */
export interface CodeIssued {
  challenge_id: string;
  phone_number: string;
  code_length: number;
  expires_in: number;
  resend_after: number;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const E164_PATTERN = /^\+[1-9]\d{6,14}$/;

/**
 * How long the browser remembers the pending code. A registration can be resent
 * for an hour (the API's OTP_REGISTRATION_WINDOW_SECONDS) without the form being
 * filled in again; a sign-in code just needs to outlive its own expiry.
 */
const MAX_AGE: Record<ChallengePurpose, number> = { register: 60 * 60, login: 30 * 60 };

export async function storeChallenge(purpose: ChallengePurpose, issued: CodeIssued, remember = false) {
  const now = Date.now();
  const stored: StoredChallenge = {
    purpose,
    id: issued.challenge_id,
    phoneNumber: issued.phone_number,
    codeLength: issued.code_length,
    expiresAt: now + issued.expires_in * 1000,
    resendAt: now + issued.resend_after * 1000,
    remember,
  };
  (await cookies()).set(OTP_CHALLENGE_COOKIE, JSON.stringify(stored), { ...baseCookie, maxAge: MAX_AGE[purpose] });
}

/** Push the resend countdown forward after the API said to wait. */
export async function delayResend(purpose: ChallengePurpose, retryAfterSeconds: number) {
  const stored = await readChallenge(purpose);
  if (!stored) return;
  stored.resendAt = Date.now() + retryAfterSeconds * 1000;
  (await cookies()).set(OTP_CHALLENGE_COOKIE, JSON.stringify(stored), { ...baseCookie, maxAge: MAX_AGE[purpose] });
}

/** The pending challenge for `purpose`, if this browser has a well-formed one. */
export async function readChallenge(purpose: ChallengePurpose): Promise<StoredChallenge | undefined> {
  const raw = (await cookies()).get(OTP_CHALLENGE_COOKIE)?.value;
  if (!raw || raw.length > 1024) return undefined;
  try {
    const value = JSON.parse(raw) as Partial<StoredChallenge>;
    if (
      value.purpose !== purpose ||
      typeof value.id !== "string" ||
      !UUID_PATTERN.test(value.id) ||
      typeof value.phoneNumber !== "string" ||
      !E164_PATTERN.test(value.phoneNumber) ||
      typeof value.codeLength !== "number" ||
      typeof value.expiresAt !== "number" ||
      typeof value.resendAt !== "number"
    ) {
      return undefined;
    }
    return { ...(value as StoredChallenge), remember: value.remember === true };
  } catch {
    return undefined;
  }
}

export async function clearChallenge() {
  (await cookies()).delete(OTP_CHALLENGE_COOKIE);
}

export function pendingView(stored: StoredChallenge): PendingCode {
  return {
    purpose: stored.purpose,
    phoneNumber: stored.phoneNumber,
    maskedPhone: maskPhoneNumber(stored.phoneNumber),
    codeLength: stored.codeLength,
    expiresAt: stored.expiresAt,
    resendAt: stored.resendAt,
  };
}

/** The pending code screen for `purpose`, for a page to render after a refresh. */
export async function pendingCode(purpose: ChallengePurpose): Promise<PendingCode | undefined> {
  const stored = await readChallenge(purpose);
  return stored ? pendingView(stored) : undefined;
}
