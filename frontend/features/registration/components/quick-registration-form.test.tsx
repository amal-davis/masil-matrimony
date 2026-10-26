import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QuickRegistrationForm } from "./quick-registration-form";

const actions = vi.hoisted(() => ({ registerMember: vi.fn() }));
vi.mock("@/features/auth/actions", () => actions);

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText("Profile created for"), "self");
  await user.click(screen.getByLabelText("Female"));
  await user.type(screen.getByLabelText("Full name"), "Lekha Das");
  await user.type(screen.getByLabelText("Date of birth"), `${new Date().getFullYear() - 26}-01-01`);
  await user.type(screen.getByLabelText("Mobile number"), "98123 45600");
  await user.type(screen.getByLabelText("Email address"), "lekha@example.com");
  await user.click(screen.getByRole("checkbox"));
}

describe("QuickRegistrationForm", () => {
  it("has no password field, and asks for an email address", () => {
    render(<QuickRegistrationForm />);
    expect(screen.queryByLabelText(/password/i)).toBeNull();
    expect(screen.getByLabelText("Email address")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Country code: India \+91/ })).toBeTruthy();
  });

  it("reports invalid fields without calling the server", async () => {
    const user = userEvent.setup();
    render(<QuickRegistrationForm />);
    await user.type(screen.getByLabelText("Mobile number"), "12345");
    await user.click(screen.getByRole("button", { name: "Register free" }));
    expect(await screen.findByText("Enter a valid 10-digit Indian mobile number, e.g. 98765 43210.")).toBeTruthy();
    expect(screen.getByText("Please accept the terms and privacy policy.")).toBeTruthy();
    expect(screen.getByText("Enter your email address. We send your payment receipts there.")).toBeTruthy();
    expect(actions.registerMember).not.toHaveBeenCalled();
  });

  it("sends the details and shows a loading state", async () => {
    const user = userEvent.setup();
    actions.registerMember.mockReturnValue(new Promise(() => {})); // the action redirects on success
    render(<QuickRegistrationForm />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Register free" }));

    const busy = await screen.findByRole("button", { name: "Sending verification code…" });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    expect(actions.registerMember).toHaveBeenCalledWith(
      expect.objectContaining({ country: "IN", mobile: "98123 45600", email: "lekha@example.com", fullName: "Lekha Das" }),
    );
  });

  it("directs an already-registered number to log in", async () => {
    const user = userEvent.setup();
    actions.registerMember.mockResolvedValue({
      ok: false,
      phoneRegistered: true,
      fieldErrors: { mobile: "An account already uses this mobile number. Please log in instead." },
    });
    render(<QuickRegistrationForm />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Register free" }));
    expect(await screen.findByText("An account already uses this mobile number. Please log in instead.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Log in with this number" }).getAttribute("href")).toBe("/login");
  });

  it("shows SMS provider failures", async () => {
    const user = userEvent.setup();
    actions.registerMember.mockResolvedValue({
      ok: false,
      message: "We can't send SMS codes right now. Please try again later, or contact us.",
    });
    render(<QuickRegistrationForm />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Register free" }));
    expect((await screen.findByRole("alert")).textContent).toContain("can't send SMS codes");
  });
});
