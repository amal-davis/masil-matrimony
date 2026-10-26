/**
 * Stand-in for ./actions.ts in the GitHub Pages static preview, which can't
 * contain Server Actions (.github/workflows/deploy-pages.yml copies this file
 * over actions.ts before building). In preview builds the sign-in forms never
 * call these (they run their "design preview" path instead); they exist so the
 * pages compile, and refuse if called. Keep the exports in step with actions.ts.
 */

import type { QuickRegistrationInput } from "@/features/registration/schema";

import type { PendingCode } from "./challenge";
import type { ChangeMobileInput, LoginPhoneInput } from "./schema";

export type { PendingCode };

export type SendCodeResult =
  | { ok: true; pending: PendingCode }
  | {
      ok: false;
      message: string;
      field?: "phone";
      retryAfter?: number;
      expired?: boolean;
      phoneRegistered?: boolean;
    };

export type VerifyFailure = "incorrect" | "expired" | "used" | "attempts" | "invalid" | "conflict" | "error";

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

const MESSAGE = "Signing in isn't available in the website preview.";

export async function requestLoginCode(values: LoginPhoneInput): Promise<SendCodeResult> {
  void values;
  return { ok: false, message: MESSAGE };
}

export async function resendLoginCode(): Promise<SendCodeResult> {
  return { ok: false, message: MESSAGE };
}

export async function verifyLoginCode(code: string, next?: string): Promise<VerifyCodeResult> {
  void code;
  void next;
  return { ok: false, reason: "error", message: MESSAGE };
}

export async function cancelPendingCode(): Promise<void> {}

export async function registerMember(values: QuickRegistrationInput): Promise<RegisterResult> {
  void values;
  return { ok: false, message: "Registration isn't available in the website preview." };
}

export async function resendRegistrationCode(change?: ChangeMobileInput): Promise<SendCodeResult> {
  void change;
  return { ok: false, message: MESSAGE };
}

export async function verifyRegistrationCode(code: string): Promise<VerifyCodeResult> {
  void code;
  return { ok: false, reason: "error", message: MESSAGE };
}
