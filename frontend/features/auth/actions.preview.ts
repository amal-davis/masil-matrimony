/**
 * Stand-in for ./actions.ts in the GitHub Pages static preview, which can't
 * contain Server Actions (.github/workflows/deploy-pages.yml copies this file
 * over actions.ts before building). In preview builds the sign-in forms never
 * call these (they run their "design preview" path instead); they exist so the
 * pages compile, and refuse if called. Keep the exports in step with actions.ts.
 */

import type { QuickRegistrationInput } from "@/features/registration/schema";

import type { LoginValues } from "./schema";

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

const MESSAGE = "Sign-in isn't available in the website preview.";

export async function signIn(values: LoginValues, next?: string): Promise<SignInResult> {
  void values;
  void next;
  return { ok: false, message: MESSAGE };
}

export async function registerMember(values: QuickRegistrationInput): Promise<RegisterResult> {
  void values;
  return { ok: false, message: "Registration isn't available in the website preview." };
}

export async function requestPasswordReset(email: string): Promise<ForgotPasswordResult> {
  void email;
  return { ok: false, message: MESSAGE };
}

export async function resetPassword(
  uid: string,
  token: string,
  password: string,
  confirm: string,
): Promise<ResetPasswordResult> {
  void uid;
  void token;
  void password;
  void confirm;
  return { ok: false, reason: "error", message: MESSAGE };
}

export async function resendVerification(email?: string): Promise<ResendVerificationResult> {
  void email;
  return { ok: false, message: MESSAGE };
}

export async function changeUnverifiedEmail(password: string, newEmail: string): Promise<ChangeEmailResult> {
  void password;
  void newEmail;
  return { ok: false, message: MESSAGE };
}

export async function verifyEmail(token: string): Promise<VerifyEmailResult> {
  void token;
  return { ok: false, reason: "error", message: MESSAGE };
}
