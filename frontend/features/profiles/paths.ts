/** URL of a member's profile page, e.g. /profile/MM100234. */
export const profilePath = (profileCode: string) => `/profile/${encodeURIComponent(profileCode)}`;
