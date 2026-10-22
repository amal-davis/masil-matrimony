/**
 * Stand-in for ./actions.ts in the GitHub Pages static preview, which can't
 * contain Server Actions (see .github/workflows/deploy-pages.yml, which copies
 * this file over actions.ts before building). The preview has no member area
 * or API, and its sample profiles never call these, so each simply reports
 * that it's unavailable. Keep the exported names in step with actions.ts.
 */
import type { MutationResult } from "./server-api";

const unavailable = async (...args: unknown[]): Promise<MutationResult<never>> => {
  void args;
  return { ok: false, status: 503, message: "This isn't available in the website preview.", fieldErrors: {} };
};

export const createProfile = unavailable;
export const updateProfile = unavailable;
export const updatePartnerPreference = unavailable;
export const submitProfileForReview = unavailable;
export const setPrimaryPhoto = unavailable;
export const deletePhoto = unavailable;
export const respondToInterest = unavailable;
export const withdrawInterest = unavailable;
export const sendInterest = unavailable;
export const addToShortlist = unavailable;
export const removeFromShortlist = unavailable;
export const markNotificationRead = unavailable;
export const markAllNotificationsRead = unavailable;
