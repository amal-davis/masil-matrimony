import { describe, expect, it } from "vitest";

import { quickRegistrationSchema } from "@/features/registration/schema";

import { safeRedirectPath } from "./redirect";
import { loginPhoneSchema, maskPhoneNumber, OTP_PATTERN, toMobileE164 } from "./schema";

describe("toMobileE164", () => {
  it("accepts common ways of writing an Indian mobile number", () => {
    for (const typed of ["9876543210", "98765 43210", "098765-43210", "+91 98765 43210", "+919876543210"]) {
      expect(toMobileE164(typed, "IN")).toBe("+919876543210");
    }
  });

  it("rejects numbers that aren't Indian mobiles", () => {
    for (const typed of ["5876543210", "987654321", "98765432101", "abc", "", "+447911123456"]) {
      expect(toMobileE164(typed, "IN")).toBeNull();
    }
  });

  it("only allows the configured countries (India by default)", () => {
    expect(toMobileE164("50 123 4567", "AE")).toBeNull();
  });
});

describe("loginPhoneSchema", () => {
  it("normalises the number and keeps the remember choice", () => {
    const parsed = loginPhoneSchema.parse({ country: "IN", phone: " 98765 43210 ", remember: true });
    expect(parsed).toEqual({ phoneNumber: "+919876543210", remember: true });
  });

  it("explains an invalid number on the phone field", () => {
    const result = loginPhoneSchema.safeParse({ country: "IN", phone: "12345", remember: false });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]).toMatchObject({
      path: ["phone"],
      message: "Enter a valid 10-digit Indian mobile number, e.g. 98765 43210.",
    });
  });

  it("requires a number", () => {
    const result = loginPhoneSchema.safeParse({ country: "IN", phone: "", remember: false });
    expect(result.error?.issues[0].message).toBe("Enter your mobile number.");
  });
});

describe("quickRegistrationSchema", () => {
  const valid = {
    createdFor: "self",
    gender: "female",
    fullName: "Lekha Das",
    dateOfBirth: `${new Date().getFullYear() - 26}-01-01`,
    country: "IN",
    mobile: "98123 45600",
    email: "lekha@example.com",
    acceptTerms: true,
  } as const;

  it("needs no password, but requires an email address", () => {
    expect(quickRegistrationSchema.safeParse(valid).success).toBe(true);
    const missing = quickRegistrationSchema.safeParse({ ...valid, email: "  " });
    expect(missing.error?.issues[0]).toMatchObject({
      path: ["email"],
      message: "Enter your email address. We send your payment receipts there.",
    });
  });

  it("rejects an invalid email, mobile, minimum age and unaccepted terms", () => {
    const fieldOf = (overrides: object) =>
      quickRegistrationSchema.safeParse({ ...valid, ...overrides }).error?.issues.map((issue) => issue.path[0]);
    expect(fieldOf({ email: "not-an-email" })).toContain("email");
    expect(fieldOf({ mobile: "12345" })).toContain("mobile");
    expect(fieldOf({ dateOfBirth: `${new Date().getFullYear() - 16}-01-01` })).toContain("dateOfBirth");
    expect(fieldOf({ acceptTerms: false })).toContain("acceptTerms");
  });
});

describe("helpers", () => {
  it("masks all but the last four digits", () => {
    expect(maskPhoneNumber("+919876543210")).toBe("+91 ••••• •3210");
  });

  it("accepts only digit codes", () => {
    expect(OTP_PATTERN.test("123456")).toBe(true);
    expect(OTP_PATTERN.test("12a456")).toBe(false);
  });

  it("never redirects off-site or back to the sign-in pages", () => {
    expect(safeRedirectPath("/dashboard/matches?page=2")).toBe("/dashboard/matches?page=2");
    expect(safeRedirectPath("//evil.example")).toBe("/dashboard");
    expect(safeRedirectPath("https://evil.example")).toBe("/dashboard");
    expect(safeRedirectPath("/login")).toBe("/dashboard");
    expect(safeRedirectPath("/verify-mobile")).toBe("/dashboard");
  });
});
