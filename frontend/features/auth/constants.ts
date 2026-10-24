/** HTTP-only cookies holding the API tokens. JavaScript in the browser can never read these. */
export const ACCESS_COOKIE = "mm_access";
export const REFRESH_COOKIE = "mm_refresh";

/**
 * Readable "1" flag set alongside the token cookies so the header can show the
 * signed-in state. It grants nothing: every API call is authorised by the tokens.
 */
export const SIGNED_IN_COOKIE = "mm_signed_in";

/**
 * HTTP-only "1" set only when the member ticked "Keep me signed in". Without it
 * every session cookie is a browser-session cookie, removed when the browser closes;
 * proxy.ts reads it so renewed tokens keep the member's choice.
 */
export const REMEMBER_COOKIE = "mm_remember";

/** Where members land after signing in when no (safe) destination was requested. */
export const DEFAULT_AFTER_LOGIN = "/dashboard";

export const LOGIN_PATH = "/login";

export const FORGOT_PASSWORD_PATH = "/forgot-password";

/** Emailed reset links point here (backend/apps/accounts/password_auth.py). */
export const RESET_PASSWORD_PATH = "/reset-password";

export const DASHBOARD_PATH = "/dashboard";

/** Shown after registering, and when an unverified member signs in. */
export const CHECK_EMAIL_PATH = "/check-email";

/** Emailed verification links point here (backend/apps/accounts/email_verification.py). */
export const VERIFY_EMAIL_PATH = "/verify-email";

/**
 * HTTP-only cookie with the address waiting for verification, so the "Check your
 * email" page can show it and resend without retyping. It grants nothing: every
 * request it feeds is checked by the API.
 */
export const PENDING_EMAIL_COOKIE = "mm_pending_email";

/** The login page, returning to `path` (a path on this site) afterwards. */
export const loginUrl = (path: string) => `${LOGIN_PATH}?next=${encodeURIComponent(path)}`;
