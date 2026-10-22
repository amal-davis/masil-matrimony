/** HTTP-only cookies holding the API tokens. JavaScript in the browser can never read these. */
export const ACCESS_COOKIE = "mm_access";
export const REFRESH_COOKIE = "mm_refresh";

/**
 * Readable "1" flag set alongside the token cookies so the header can show the
 * signed-in state. It grants nothing: every API call is authorised by the tokens.
 */
export const SIGNED_IN_COOKIE = "mm_signed_in";

/** Where members land after signing in when no (safe) destination was requested. */
export const DEFAULT_AFTER_LOGIN = "/dashboard";

export const LOGIN_PATH = "/login";

export const DASHBOARD_PATH = "/dashboard";

/** The login page, returning to `path` (a path on this site) afterwards. */
export const loginUrl = (path: string) => `${LOGIN_PATH}?next=${encodeURIComponent(path)}`;
