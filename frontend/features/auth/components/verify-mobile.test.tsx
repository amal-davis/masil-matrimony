import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PendingCode } from "../actions";
import { VerifyMobile } from "./verify-mobile";

const actions = vi.hoisted(() => ({
  resendRegistrationCode: vi.fn(),
  verifyRegistrationCode: vi.fn(),
}));
vi.mock("../actions", () => actions);

const pending: PendingCode = {
  purpose: "register",
  phoneNumber: "+919812345600",
  maskedPhone: "+91 ••••• •5600",
  codeLength: 6,
  expiresAt: Date.now() + 300_000,
  resendAt: Date.now() + 60_000,
};

describe("VerifyMobile", () => {
  it("sends visitors without a pending registration back to the form", () => {
    render(<VerifyMobile />);
    expect(screen.getByRole("alert").textContent).toContain("no registration waiting");
    expect(screen.getByRole("link", { name: "Go to the registration form" }).getAttribute("href")).toBe("/#register");
  });

  it("verifies the code with the registration action", async () => {
    const user = userEvent.setup();
    actions.verifyRegistrationCode.mockResolvedValue({ ok: false, reason: "expired", message: "This code has expired. Please request a new one." });
    render(<VerifyMobile initialPending={pending} />);
    expect(screen.getByText("+91 ••••• •5600")).toBeTruthy();
    await user.type(screen.getByLabelText("Verification code"), "654321");
    await user.click(screen.getByRole("button", { name: "Verify & create account" }));
    expect(actions.verifyRegistrationCode).toHaveBeenCalledWith("654321");
    expect((await screen.findByRole("alert")).textContent).toContain("expired");
  });

  it("changes the number without losing the registration", async () => {
    const user = userEvent.setup();
    actions.resendRegistrationCode.mockResolvedValue({
      ok: true,
      pending: { ...pending, phoneNumber: "+919812345699", maskedPhone: "+91 ••••• •5699" },
    });
    render(<VerifyMobile initialPending={pending} />);
    await user.click(screen.getByRole("button", { name: "Change mobile number" }));

    const field = screen.getByLabelText("Correct mobile number") as HTMLInputElement;
    expect(field.value).toBe("098123 45600"); // prefilled with the number being registered
    await user.clear(field);
    await user.type(field, "98123 45699");
    await user.click(screen.getByRole("button", { name: "Send code to this number" }));

    expect(actions.resendRegistrationCode).toHaveBeenCalledWith({ country: "IN", phone: "98123 45699" });
    expect(await screen.findByText("+91 ••••• •5699")).toBeTruthy();
    expect(screen.getByText(/code sent to the old number no longer works/)).toBeTruthy();
  });

  it("offers to log in when the corrected number is already registered", async () => {
    const user = userEvent.setup();
    actions.resendRegistrationCode.mockResolvedValue({
      ok: false,
      field: "phone",
      phoneRegistered: true,
      message: "An account already uses this mobile number. Please log in instead.",
    });
    render(<VerifyMobile initialPending={pending} />);
    await user.click(screen.getByRole("button", { name: "Change mobile number" }));
    const field = screen.getByLabelText("Correct mobile number");
    await user.clear(field);
    await user.type(field, "9876543210");
    await user.click(screen.getByRole("button", { name: "Send code to this number" }));
    expect(await screen.findByText("An account already uses this mobile number. Please log in instead.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Log in with this number instead" }).getAttribute("href")).toBe("/login");
  });

  it("starts again when the registration has expired", async () => {
    const user = userEvent.setup();
    actions.resendRegistrationCode.mockResolvedValue({
      ok: false,
      expired: true,
      message: "Your registration has expired. Please fill in the form again.",
    });
    render(<VerifyMobile initialPending={{ ...pending, resendAt: Date.now() - 1 }} />);
    await user.click(await screen.findByRole("button", { name: "Resend code" }));
    expect((await screen.findByRole("alert")).textContent).toContain("registration has expired");
    expect(screen.getByRole("link", { name: "Go to the registration form" })).toBeTruthy();
  });
});
