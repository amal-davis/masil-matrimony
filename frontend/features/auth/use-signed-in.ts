"use client";

import { useSyncExternalStore } from "react";

import { SIGNED_IN_COOKIE } from "./constants";

// Cookies have no change event; the value is re-read whenever the component renders
// (e.g. on navigation), and logging in or out always navigates.
const subscribe = () => () => {};
const getSignedIn = () => document.cookie.split("; ").includes(`${SIGNED_IN_COOKIE}=1`);
const getServerSignedIn = () => false;

/**
 * Whether this browser has a session, for showing "Log out" instead of "Login".
 * A display hint only: the API decides what a visitor may do.
 */
export function useSignedIn(): boolean {
  return useSyncExternalStore(subscribe, getSignedIn, getServerSignedIn);
}
