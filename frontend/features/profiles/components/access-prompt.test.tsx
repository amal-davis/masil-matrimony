import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMemberProfile } from "../member-api";
import { AccessPrompt } from "./access-prompt";

// The real client checks .env.local on import; this stands in for it, with the same ApiError shape.
const { client, ApiError, session } = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public body: Record<string, unknown> | null = null,
    ) {
      super(message);
    }
  }
  return { client: { get: vi.fn() }, ApiError, session: { token: "token" as string | undefined } };
});
vi.mock("@/lib/api/client", () => ({ api: client, ApiError }));
vi.mock("@/features/auth/session", () => ({ accessToken: async () => session.token }));

const basic = {
  profile_code: "MM706381",
  display_name: "Anu",
  gender: "female",
  age: 27,
  education: "B.Tech",
  location: { city: "Thrissur", district: "Thrissur", state: "Kerala", country: "" },
  photo: { url: "https://api.example/p/1", width: 400, height: 500 },
  photos: [{ url: "https://api.example/p/1", width: 400, height: 500 }],
  photos_hidden: false,
};

beforeEach(() => {
  client.get.mockReset();
  session.token = "token";
});

describe("AccessPrompt", () => {
  it("asks visitors to register or sign in, returning to the same profile", () => {
    render(<AccessPrompt access={{ level: "public", reason: "signed_out" }} name="Anu" path="/profile/MM706381" />);
    expect(screen.getByRole("heading").textContent).toBe("See more of Anu's profile");
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toBe(
      `/login?next=${encodeURIComponent("/profile/MM706381")}`,
    );
    expect(screen.getByRole("link", { name: "Register free" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "View membership plans" })).toBeNull();
  });

  it("offers membership plans to members with the limited view", () => {
    render(<AccessPrompt access={{ level: "limited", reason: "no_membership" }} name="Anu" path="/profile/MM706381" />);
    expect(screen.getByRole("heading").textContent).toBe("Unlock Anu's full profile");
    expect(screen.getByRole("link", { name: "View membership plans" }).getAttribute("href")).toBe("/our-packages");
    expect(screen.queryByRole("link", { name: "Sign in" })).toBeNull();
  });
});

describe("getMemberProfile", () => {
  it("asks the API as the visitor (no token) and keeps the restricted sections absent", async () => {
    session.token = undefined;
    client.get.mockResolvedValue({ ...basic, access: { level: "public", reason: "signed_out" }, viewer: null });
    const result = await getMemberProfile("mm706381");
    expect(client.get).toHaveBeenCalledWith("/profiles/MM706381/", { headers: {}, cache: "no-store" });
    if (result.kind !== "found") throw new Error(result.kind);
    expect(result.access.level).toBe("public");
    expect(result.viewer).toBeNull();
    expect(result.profile.photos).toHaveLength(1);
    for (const section of ["about", "career", "family", "lifestyle", "partnerPreferences"] as const) {
      expect(result.profile[section]).toBeUndefined();
    }
  });

  it("sends the session for members and passes the API's access decision through", async () => {
    client.get.mockResolvedValue({
      ...basic,
      access: { level: "full", reason: "membership" },
      about: "About Anu",
      career: { qualification: "B.Tech", institution: "", profession: "Engineer", employment_type: "", work_location: "", annual_income: "" },
      viewer: { is_own_profile: false, interest_sent: null, interest_received: null, shortlisted: false, contact: null },
    });
    const result = await getMemberProfile("MM706381");
    expect(client.get.mock.calls[0][1]).toEqual({ headers: { Authorization: "Bearer token" }, cache: "no-store" });
    if (result.kind !== "found") throw new Error(result.kind);
    expect(result.access.level).toBe("full");
    expect(result.profile.about).toBe("About Anu");
    expect(result.profile.career?.profession).toBe("Engineer");
  });

  it("shows the sign-in gate when the API refuses a visitor", async () => {
    session.token = undefined;
    client.get.mockRejectedValue(new ApiError(401, "Sign in", { code: "sign_in_required" }));
    expect((await getMemberProfile("MM706381")).kind).toBe("signed_out");
  });
});
