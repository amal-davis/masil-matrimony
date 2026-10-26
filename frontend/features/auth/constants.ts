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

/**
 * HTTP-only cookie with the SMS code this browser is waiting for (sign-in or
 * registration): the challenge id and what the code screen shows. It lets that
 * screen survive a page refresh while keeping the challenge id away from browser
 * JavaScript. It grants nothing on its own: the API needs the code from the SMS.
 */
export const OTP_CHALLENGE_COOKIE = "mm_otp";

/** Where members land after signing in when no (safe) destination was requested. */
export const DEFAULT_AFTER_LOGIN = "/dashboard";

/** New members land on their profile, to finish it. */
export const AFTER_REGISTER = "/dashboard/my-profile";

export const LOGIN_PATH = "/login";

/** The registration form is in the homepage hero. */
export const REGISTER_PATH = "/#register";

/** Entering the SMS code that completes a registration. */
export const VERIFY_MOBILE_PATH = "/verify-mobile";

export const DASHBOARD_PATH = "/dashboard";

/** The login page, returning to `path` (a path on this site) afterwards. */
export const loginUrl = (path: string) => `${LOGIN_PATH}?next=${encodeURIComponent(path)}`;
