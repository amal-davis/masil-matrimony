import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CheckoutOptions } from "@/features/dashboard/types";

import { loadRazorpay, openCheckout } from "../razorpay-checkout";
import { PayButton } from "./pay-button";

const actions = vi.hoisted(() => ({ startPurchase: vi.fn(), verifyPayment: vi.fn() }));
vi.mock("@/features/dashboard/actions", () => actions);
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const checkout: CheckoutOptions = {
  key: "rzp_test_FAKE",
  order_id: "order_TEST1",
  amount: 11800000,
  currency: "INR",
  name: "Massil Matrimony",
  description: "Royal (12 months)",
  prefill: { name: "Anu", email: "anu@example.com", contact: "+919800000000" },
  test_mode: true,
};
const started = { ok: true, data: { purchase: { reference: "MMP-20261026-ABCDEFGH" }, checkout } };
const success = { razorpay_order_id: "order_TEST1", razorpay_payment_id: "pay_TEST1", razorpay_signature: "a".repeat(64) };

/** A stand-in for window.Razorpay that lets each test act as the member in the payment window. */
class FakeRazorpay {
  static last: FakeRazorpay;
  failed?: (response: { error: { description: string } }) => void;
  constructor(public options: Record<string, unknown> & { handler: (r: unknown) => void; modal: { ondismiss: () => void } }) {
    FakeRazorpay.last = this;
  }
  on(_event: string, handler: FakeRazorpay["failed"]) {
    this.failed = handler;
  }
  open() {}
}

beforeEach(() => {
  window.Razorpay = FakeRazorpay as unknown as Window["Razorpay"];
  actions.startPurchase.mockResolvedValue(started);
  actions.verifyPayment.mockResolvedValue({ ok: true, data: {} });
});
afterEach(() => {
  delete window.Razorpay;
  push.mockReset();
});

describe("PayButton", () => {
  it("opens Razorpay with the server's order and sends only the package code", async () => {
    const user = userEvent.setup();
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    expect(actions.startPurchase).toHaveBeenCalledWith("royal");
    expect(FakeRazorpay.last.options).toMatchObject({ key: "rzp_test_FAKE", order_id: "order_TEST1", amount: 11800000 });
    expect(screen.getByRole("button", { name: "Payment window open…" })).toBeTruthy();
  });

  it("lets the server decide: after paying it goes to the purchase page, never claiming success itself", async () => {
    const user = userEvent.setup();
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    await act(async () => FakeRazorpay.last.options.handler(success));
    expect(actions.verifyPayment).toHaveBeenCalledWith("MMP-20261026-ABCDEFGH", success);
    expect(push).toHaveBeenCalledWith("/dashboard/membership/purchases/MMP-20261026-ABCDEFGH?from=checkout");
    expect(screen.queryByText(/payment (received|successful)/i)).toBeNull();
  });

  it("starts only one checkout for repeated clicks", async () => {
    const user = userEvent.setup();
    let resolve!: (value: unknown) => void;
    actions.startPurchase.mockReturnValue(new Promise((done) => (resolve = done)));
    render(<PayButton packageCode="royal" label="Pay now" />);
    const button = screen.getByRole("button", { name: "Pay now" });
    await user.click(button);
    await user.click(button);
    expect(screen.getByRole("button", { name: "Preparing secure payment…" })).toHaveProperty("disabled", true);
    await act(async () => resolve(started));
    expect(actions.startPurchase).toHaveBeenCalledTimes(1);
  });

  it("explains a closed payment window and offers the purchase", async () => {
    const user = userEvent.setup();
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    await act(async () => FakeRazorpay.last.options.modal.ondismiss());
    expect(screen.getByText(/closed before a payment was completed/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "View this purchase" }).getAttribute("href")).toBe(
      "/dashboard/membership/purchases/MMP-20261026-ABCDEFGH",
    );
    expect(actions.verifyPayment).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Pay now" })).toHaveProperty("disabled", false);
  });

  it("reports a failed attempt while the window stays open", async () => {
    const user = userEvent.setup();
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    act(() => FakeRazorpay.last.failed!({ error: { description: "Your bank declined the payment." } }));
    expect(screen.getByText(/That payment attempt failed: Your bank declined the payment\./)).toBeTruthy();
  });

  it("shows the API's reason when checkout can't start", async () => {
    const user = userEvent.setup();
    actions.startPurchase.mockResolvedValue({ ok: false, status: 409, message: "You already have an active membership.", fieldErrors: {} });
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    expect(screen.getByText("You already have an active membership.")).toBeTruthy();
    expect(actions.verifyPayment).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a rejected verification instead of navigating", async () => {
    const user = userEvent.setup();
    actions.verifyPayment.mockResolvedValue({ ok: false, status: 400, message: "We couldn't verify this payment.", fieldErrors: {} });
    render(<PayButton packageCode="royal" label="Pay now" />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    await act(async () => FakeRazorpay.last.options.handler(success));
    expect(screen.getByText(/We couldn't verify this payment\./)).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });

  it("requires accepting the terms when asked", async () => {
    const user = userEvent.setup();
    render(<PayButton packageCode="royal" label="Pay now" requireConsent />);
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    expect(screen.getByText("Please accept the terms and refund policy to continue.")).toBeTruthy();
    expect(actions.startPurchase).not.toHaveBeenCalled();
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Pay now" }));
    expect(actions.startPurchase).toHaveBeenCalledTimes(1);
  });

  it("reuses an existing order without starting a new purchase", async () => {
    const user = userEvent.setup();
    render(<PayButton existing={{ reference: "MMP-20261026-ABCDEFGH", checkout }} label="Try again" />);
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(actions.startPurchase).not.toHaveBeenCalled();
    expect(FakeRazorpay.last.options.order_id).toBe("order_TEST1");
  });
});

describe("razorpay-checkout", () => {
  it("resolves on the first outcome only", async () => {
    const outcome = openCheckout(checkout, () => {});
    FakeRazorpay.last.options.handler(success);
    FakeRazorpay.last.options.modal.ondismiss();
    expect(await outcome).toEqual({ kind: "success", response: success });
  });

  it("loads the official script once and reports load failures", async () => {
    delete window.Razorpay;
    const loading = loadRazorpay(1000);
    const script = document.querySelector<HTMLScriptElement>('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    expect(script).toBeTruthy();
    script!.onerror!(new Event("error"));
    await expect(loading).rejects.toThrow("couldn't be loaded");
  });
});
