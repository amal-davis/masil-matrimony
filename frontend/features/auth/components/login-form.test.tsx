import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PendingCode, SendCodeResult, VerifyCodeResult } from "../actions";
import { LoginForm } from "./login-form";

const actions = vi.hoisted(() => ({
  requestLoginCode: vi.fn(),
  resendLoginCode: vi.fn(),
  verifyLoginCode: vi.fn(),
  cancelPendingCode: vi.fn(),
}));
vi.mock("../actions", () => actions);
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function pendingCode(overrides: Partial<PendingCode> = {}): PendingCode {
  return {
    purpose: "login",
    phoneNumber: "+919876543210",
    maskedPhone: "+91 ••••• •3210",
    codeLength: 6,
    expiresAt: Date.now() + 300_000,
    resendAt: Date.now() + 60_000,
    ...overrides,
  };
}

/** A promise the test resolves, to look at the loading state in between. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

const codeField = () => screen.getByLabelText("Verification code");

describe("LoginForm: mobile number step", () => {
  beforeEach(() => {
    actions.cancelPendingCode.mockResolvedValue(undefined);
  });

  it("validates the number before calling the server", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.type(screen.getByLabelText("Mobile number"), "12345");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByText("Enter a valid 10-digit Indian mobile number, e.g. 98765 43210.")).toBeTruthy();
    expect(actions.requestLoginCode).not.toHaveBeenCalled();
  });

  it("shows a loading state, then the code step for the masked number", async () => {
    const user = userEvent.setup();
    const reply = deferred<SendCodeResult>();
    actions.requestLoginCode.mockReturnValue(reply.promise);
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Mobile number"), "98765 43210");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    const busy = await screen.findByRole("button", { name: "Sending code…" });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    expect(actions.requestLoginCode).toHaveBeenCalledWith({ country: "IN", phone: "98765 43210", remember: false });

    await act(async () => reply.resolve({ ok: true, pending: pendingCode() }));
    expect(await screen.findByText("+91 ••••• •3210")).toBeTruthy();
    expect(codeField()).toBeTruthy();
  });

  it("shows provider and rate-limit failures honestly", async () => {
    const user = userEvent.setup();
    actions.requestLoginCode.mockResolvedValue({
      ok: false,
      message: "We couldn't send the SMS just now. Please try again in a few minutes.",
    });
    render(<LoginForm />);
    await user.type(screen.getByLabelText("Mobile number"), "9876543210");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect((await screen.findByRole("alert")).textContent).toContain("couldn't send the SMS");
    // Still on the number step: nothing pretends a code was sent.
    expect(screen.queryByLabelText("Verification code")).toBeNull();
  });
});

describe("LoginForm: code step", () => {
  beforeEach(() => {
    actions.cancelPendingCode.mockResolvedValue(undefined);
  });

  it("resumes the code step after a refresh and accepts a pasted code", async () => {
    const user = userEvent.setup();
    actions.verifyLoginCode.mockResolvedValue({
      ok: false,
      reason: "incorrect",
      message: "That code is incorrect. Please check the SMS and try again.",
      attemptsRemaining: 4,
    } satisfies VerifyCodeResult);
    render(<LoginForm initialPending={pendingCode()} />);

    await user.click(codeField());
    await user.paste("123 456");
    expect((codeField() as HTMLInputElement).value).toBe("123456");
    await user.click(screen.getByRole("button", { name: "Verify & log in" }));

    expect(actions.verifyLoginCode).toHaveBeenCalledWith("123456", undefined);
    expect(await screen.findByText(/That code is incorrect.*4 attempts left\./)).toBeTruthy();
    expect((codeField() as HTMLInputElement).value).toBe("");
  });

  it("asks for every digit before submitting", async () => {
    const user = userEvent.setup();
    render(<LoginForm initialPending={pendingCode()} />);
    await user.type(codeField(), "123");
    await user.click(screen.getByRole("button", { name: "Verify & log in" }));
    expect(await screen.findByText("Enter all 6 digits of the code.")).toBeTruthy();
    expect(actions.verifyLoginCode).not.toHaveBeenCalled();
  });

  it("disables the code once it is used up, and offers a new one", async () => {
    const user = userEvent.setup();
    actions.verifyLoginCode.mockResolvedValue({
      ok: false,
      reason: "attempts",
      message: "Too many incorrect attempts. Please request a new code.",
    });
    render(<LoginForm initialPending={pendingCode({ resendAt: Date.now() - 1 })} />);
    await user.type(codeField(), "123456");
    await user.click(screen.getByRole("button", { name: "Verify & log in" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Too many incorrect attempts");
    expect((screen.getByRole("button", { name: "Verify & log in" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Resend code" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows an expired code as expired", async () => {
    render(<LoginForm initialPending={pendingCode({ expiresAt: Date.now() - 1, resendAt: Date.now() - 1 })} />);
    expect(await screen.findByText("This code has expired. Request a new code below.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Verify & log in" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps Resend disabled during the cooldown, then sends a new code", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      actions.resendLoginCode.mockResolvedValue({ ok: true, pending: pendingCode() });
      render(<LoginForm initialPending={pendingCode({ resendAt: Date.now() + 3_000 })} />);

      const resend = await screen.findByRole("button", { name: /Resend code.*in 0:0\d/ });
      expect((resend as HTMLButtonElement).disabled).toBe(true);

      await act(async () => vi.advanceTimersByTime(4_000));
      const ready = await screen.findByRole("button", { name: "Resend code" });
      expect((ready as HTMLButtonElement).disabled).toBe(false);
      await user.click(ready);
      expect(actions.resendLoginCode).toHaveBeenCalledOnce();
      expect(await screen.findByText(/A new code has been sent to \+91 ••••• •3210/)).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("goes back to the number step to change the number", async () => {
    const user = userEvent.setup();
    render(<LoginForm initialPending={pendingCode()} />);
    await user.click(screen.getByRole("button", { name: "Change mobile number" }));
    await waitFor(() => expect(screen.getByLabelText("Mobile number")).toBeTruthy());
    expect(actions.cancelPendingCode).toHaveBeenCalledOnce();
  });
});
