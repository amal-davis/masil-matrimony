/**
 * Stand-in for ./actions.ts in the GitHub Pages static preview, which can't
 * contain Server Actions (.github/workflows/deploy-pages.yml copies this file
 * over actions.ts before building). In preview builds the login flow never
 * calls these (it runs its "design preview" path instead); they exist so the
 * page compiles, and refuse if called. Keep the exports in step with actions.ts.
 */

export type RequestCodeResult =
  | { ok: true; challengeId: string; codeLength: number; expiresIn: number; resendAfter: number }
  | { ok: false; message: string; field?: "phone"; retryAfter?: number };

export type VerifyFailure = "incorrect" | "expired" | "used" | "attempts" | "invalid" | "error";

export type VerifyCodeResult = { ok: false; reason: VerifyFailure; message: string; attemptsRemaining?: number };

const MESSAGE = "Sign-in isn't available in the website preview.";

export async function requestLoginCode(phoneNumber: string): Promise<RequestCodeResult> {
  void phoneNumber;
  return { ok: false, message: MESSAGE };
}

export async function verifyLoginCode(challengeId: string, code: string, next?: string): Promise<VerifyCodeResult> {
  void challengeId;
  void code;
  void next;
  return { ok: false, reason: "error", message: MESSAGE };
}
