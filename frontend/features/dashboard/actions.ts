"use server";

import { refresh } from "next/cache";

import { memberMutate, type MutationResult } from "./server-api";
import type { CheckoutOptions, ContactStatus, InterestItem, OwnPhoto, OwnProfile, PartnerPreference, Purchase } from "./types";

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

/**
 * Show a member's mobile number. The API checks the membership, the member's
 * consent and the package limit, and counts the view; the number is returned
 * only to this caller and never stored in the page.
 */
export async function viewContactNumber(profileCode: string) {
  if (!PROFILE_CODE.test(profileCode)) return invalid;
  return andRefresh(memberMutate<ContactStatus>("post", `/profiles/${profileCode}/contact/`, undefined, `/profile/${profileCode}`));
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

// --- Membership purchases (backend/apps/payments) ---------------------------
// Only a package code goes to the API: it sets the price. The membership is
// activated only by the API after Razorpay confirms the payment.

const PACKAGE_CODE = /^[a-z]{2,16}$/;
const PURCHASE_REFERENCE = /^[A-Z0-9-]{8,40}$/;
const RAZORPAY_ID = /^[A-Za-z0-9_]{6,40}$/;
const SIGNATURE = /^[0-9a-f]{64}$/i;

/** Start (or resume) checkout for a package: the purchase and the options for Razorpay Checkout. */
export async function startPurchase(packageCode: string) {
  if (!PACKAGE_CODE.test(packageCode)) return invalid;
  return memberMutate<{ purchase: Purchase; checkout: CheckoutOptions }>(
    "post", "/payments/purchases/", { package: packageCode }, "/dashboard/membership",
  );
}

/** Pass Razorpay Checkout's success response to the API, which verifies it and asks Razorpay. */
export async function verifyPayment(
  reference: string,
  response: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string },
) {
  if (
    !PURCHASE_REFERENCE.test(reference) ||
    !RAZORPAY_ID.test(response?.razorpay_order_id ?? "") ||
    !RAZORPAY_ID.test(response?.razorpay_payment_id ?? "") ||
    !SIGNATURE.test(response?.razorpay_signature ?? "")
  ) {
    return invalid;
  }
  const { razorpay_order_id, razorpay_payment_id, razorpay_signature } = response;
  return andRefresh(
    memberMutate<Purchase>(
      "post",
      `/payments/purchases/${reference}/verify/`,
      { razorpay_order_id, razorpay_payment_id, razorpay_signature },
      `/dashboard/membership/purchases/${reference}`,
    ),
  );
}

/** "Check payment status": the API asks Razorpay about the order again. */
export async function refreshPaymentStatus(reference: string) {
  if (!PURCHASE_REFERENCE.test(reference)) return invalid;
  return andRefresh(
    memberMutate<Purchase>("post", `/payments/purchases/${reference}/refresh/`, undefined, `/dashboard/membership/purchases/${reference}`),
  );
}

/** The member corrects their own email address (where receipts go). */
export async function updateEmail(email: string) {
  if (typeof email !== "string" || email.length > 254) return invalid;
  return andRefresh(memberMutate<{ email: string }>("patch", "/auth/me/email/", { email: email.trim() }, "/dashboard/settings"));
}
