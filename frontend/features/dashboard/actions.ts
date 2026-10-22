"use server";

import { refresh } from "next/cache";

import { memberMutate, type MutationResult } from "./server-api";
import type { InterestItem, OwnPhoto, OwnProfile, PartnerPreference } from "./types";

/**
 * Dashboard mutations. Each one calls the member API as the signed-in member
 * (the API decides what is allowed) and refreshes the page only after the
 * server has confirmed the change. Server Actions also check the request's
 * Origin, so they can't be triggered cross-site.
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PROFILE_CODE = /^[A-Za-z0-9]{4,12}$/;

const invalid = { ok: false as const, status: 400, message: "That request wasn't valid.", fieldErrors: {} };

async function andRefresh<T>(result: Promise<MutationResult<T>>): Promise<MutationResult<T>> {
  const settled = await result;
  if (settled.ok) refresh();
  return settled;
}

// --- Profile ---------------------------------------------------------------

export type ProfileValues = Partial<Omit<OwnProfile, "partner_preference" | "completion">>;

export async function createProfile(values: ProfileValues) {
  return andRefresh(memberMutate<OwnProfile>("post", "/profiles/me/", values, "/dashboard/my-profile"));
}

export async function updateProfile(values: ProfileValues) {
  return andRefresh(memberMutate<OwnProfile>("patch", "/profiles/me/", values, "/dashboard/my-profile"));
}

export async function updatePartnerPreference(values: Partial<PartnerPreference>) {
  return andRefresh(
    memberMutate<PartnerPreference>("patch", "/profiles/me/partner-preference/", values, "/dashboard/my-profile"),
  );
}

export async function submitProfileForReview() {
  return andRefresh(memberMutate<OwnProfile>("post", "/profiles/me/submit/", undefined, "/dashboard/my-profile"));
}

// --- Photos ----------------------------------------------------------------

export async function setPrimaryPhoto(photoId: string) {
  if (!UUID.test(photoId)) return invalid;
  return andRefresh(memberMutate<OwnPhoto[]>("post", `/profiles/me/photos/${photoId}/primary/`, undefined, "/dashboard/photos"));
}

export async function deletePhoto(photoId: string) {
  if (!UUID.test(photoId)) return invalid;
  return andRefresh(memberMutate<null>("delete", `/profiles/me/photos/${photoId}/`, undefined, "/dashboard/photos"));
}

// --- Interests and shortlist ---------------------------------------------

export async function respondToInterest(interestId: string, response: "accept" | "decline") {
  if (!UUID.test(interestId) || (response !== "accept" && response !== "decline")) return invalid;
  return andRefresh(
    memberMutate<InterestItem>("post", `/interests/${interestId}/${response}/`, undefined, "/dashboard/interests/received"),
  );
}

export async function withdrawInterest(interestId: string) {
  if (!UUID.test(interestId)) return invalid;
  return andRefresh(
    memberMutate<InterestItem>("post", `/interests/${interestId}/withdraw/`, undefined, "/dashboard/interests/sent"),
  );
}

export async function sendInterest(profileCode: string) {
  if (!PROFILE_CODE.test(profileCode)) return invalid;
  return andRefresh(memberMutate<InterestItem>("post", "/interests/", { profile_code: profileCode }, `/profile/${profileCode}`));
}

export async function addToShortlist(profileCode: string) {
  if (!PROFILE_CODE.test(profileCode)) return invalid;
  return andRefresh(memberMutate<unknown>("post", "/shortlist/", { profile_code: profileCode }, "/dashboard/shortlisted"));
}

export async function removeFromShortlist(profileCode: string) {
  if (!PROFILE_CODE.test(profileCode)) return invalid;
  return andRefresh(memberMutate<null>("delete", `/shortlist/${profileCode}/`, undefined, "/dashboard/shortlisted"));
}

// --- Notifications ---------------------------------------------------------

export async function markNotificationRead(notificationId: string) {
  if (!UUID.test(notificationId)) return invalid;
  return andRefresh(memberMutate<null>("post", `/notifications/${notificationId}/read/`, undefined, "/dashboard/notifications"));
}

export async function markAllNotificationsRead() {
  return andRefresh(memberMutate<null>("post", "/notifications/read-all/", undefined, "/dashboard/notifications"));
}
