import type { CheckoutOptions } from "@/features/dashboard/types";

/**
 * Razorpay Standard Checkout in the browser: the official script, opened with
 * the order the API created. The browser never sees the key secret, never sets
 * the amount, and never decides that a payment succeeded: the success handler
 * only passes Razorpay's response to the API to verify.
 */

const SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

/** Razorpay Checkout's success response (sent to the API for verification). */
export interface CheckoutSuccess {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open(): void;
  on(event: "payment.failed", handler: (response: { error?: { description?: string } }) => void): void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

let loading: Promise<void> | null = null;

export function loadRazorpay(timeoutMs = 15_000): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Not in a browser."));
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    const timer = window.setTimeout(() => fail(), timeoutMs);
    const fail = () => {
      window.clearTimeout(timer);
      script.remove();
      loading = null; // allow another try
      reject(new Error("The payment window couldn't be loaded."));
    };
    script.onload = () => {
      window.clearTimeout(timer);
      if (window.Razorpay) resolve();
      else fail();
    };
    script.onerror = fail;
    document.body.appendChild(script);
  });
  return loading;
}

export type CheckoutOutcome = { kind: "success"; response: CheckoutSuccess } | { kind: "dismissed" };

/**
 * Open Razorpay Checkout and wait until the member pays or closes it. A failed
 * attempt keeps the window open (Razorpay lets them retry) and is reported
 * through `onFailedAttempt`.
 */
export function openCheckout(options: CheckoutOptions, onFailedAttempt: (message: string) => void): Promise<CheckoutOutcome> {
  return new Promise((resolve) => {
    if (!window.Razorpay) throw new Error("Razorpay Checkout isn't loaded.");
    let settled = false;
    const settle = (outcome: CheckoutOutcome) => {
      if (!settled) {
        settled = true;
        resolve(outcome);
      }
    };
    const checkout = new window.Razorpay({
      key: options.key,
      order_id: options.order_id,
      amount: options.amount,
      currency: options.currency,
      name: options.name,
      description: options.description,
      prefill: options.prefill,
      theme: { color: "#4b0f1e" },
      handler: (response: CheckoutSuccess) => settle({ kind: "success", response }),
      modal: { ondismiss: () => settle({ kind: "dismissed" }) },
    });
    checkout.on("payment.failed", (response) => {
      onFailedAttempt(response?.error?.description || "The payment didn't go through.");
    });
    checkout.open();
  });
}
