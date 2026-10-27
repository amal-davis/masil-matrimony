import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Entitlements } from "../types";
import { AssistanceCard } from "./assistance-card";
import { EntitlementList } from "./entitlement-list";
import { VerificationCard } from "./verification-card";

const actions = vi.hoisted(() => ({ requestVerification: vi.fn(), requestAssistance: vi.fn() }));
vi.mock("../actions", () => actions);

const free: Entitlements = {
  package_code: "free",
  package_name: "Free Membership",
  is_paid: false,
  features: {
    photo_viewing: false,
    advanced_search: false,
    messaging: false,
    profile_viewers: false,
    verification: false,
    priority_visibility: false,
    matchmaking_assistance: false,
    unlimited_interests: false,
    contact_access: false,
    basic_search: true,
    shortlist: true,
    match_suggestions: true,
  },
  outgoing_interest_limit: 15,
  outgoing_interests_used: 4,
  contact_view_limit: null,
  contact_views_used: null,
  contact_views_remaining: null,
  unavailable: [],
};

const silver: Entitlements = {
  ...free,
  package_code: "silver",
  package_name: "Silver Membership",
  is_paid: true,
  features: {
    ...(Object.fromEntries(Object.keys(free.features).map((key) => [key, true])) as Entitlements["features"]),
    priority_visibility: false,
    matchmaking_assistance: false,
  },
  outgoing_interest_limit: null,
  outgoing_interests_used: null,
  contact_view_limit: 40,
  contact_views_used: 3,
  contact_views_remaining: 37,
};

const gold: Entitlements = {
  ...silver,
  package_code: "gold",
  package_name: "Gold Membership",
  features: { ...silver.features, priority_visibility: true, matchmaking_assistance: true },
  contact_view_limit: 100,
  contact_views_used: 23,
  contact_views_remaining: 77,
};

const included = () => screen.getAllByText(": included").map((node) => node.parentElement!.firstChild!.textContent);
const locked = () => screen.getAllByText(": not included in your plan").map((node) => node.parentElement!.firstChild!.textContent);

describe("EntitlementList", () => {
  it("shows a Free member what the backend includes and what is locked", () => {
    render(<EntitlementList entitlements={free} />);
    expect(included()).toEqual(["Interests", "Profile shortlist", "Match suggestions"]);
    expect(locked()).toEqual([
      "Advanced search",
      "Personal messaging",
      "Full profiles and photo viewing",
      "Who viewed my profile",
      "Verified Profile badge (on request)",
      "Member contact numbers",
      "Priority profile visibility",
      "Matchmaking assistance",
    ]);
    expect(screen.getByText("4 of 15 used")).toBeTruthy();
  });

  it("shows Silver's features and the contact numbers left out of 40", () => {
    render(<EntitlementList entitlements={silver} />);
    expect(locked()).toEqual(["Priority profile visibility", "Matchmaking assistance"]);
    expect(screen.getByText("Unlimited interests")).toBeTruthy();
    expect(screen.getByText("37 of 40 left")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Personal messaging" }).getAttribute("href")).toBe("/dashboard/messages");
  });
});

describe("EntitlementList for Gold", () => {
  it("shows every Gold feature and 77 of 100 contact numbers left", () => {
    render(<EntitlementList entitlements={gold} />);
    expect(screen.queryByText(": not included in your plan")).toBeNull();
    expect(screen.getByText("77 of 100 left")).toBeTruthy();
    expect(screen.getByText("Priority profile visibility")).toBeTruthy();
  });

  it("says when an included benefit is switched off", () => {
    render(<EntitlementList entitlements={{ ...gold, unavailable: ["matchmaking_assistance"] }} />);
    expect(screen.getByText(": included, currently unavailable").parentElement!.firstChild!.textContent).toBe(
      "Matchmaking assistance",
    );
    expect(screen.getByText("Currently unavailable")).toBeTruthy();
  });
});

describe("AssistanceCard", () => {
  const request = {
    id: "00000000-0000-4000-a000-000000000001",
    kind: "request" as const,
    status: "requested" as const,
    status_label: "Awaiting assignment",
    is_open: true,
    member_note: "",
    requested_at: "2026-10-27T10:00:00+05:30",
    assigned: false,
    matchmaker_name: null,
    assigned_at: null,
    closed_at: null,
    message: "",
    service_active: true,
    service_starts_at: "2026-10-01T10:00:00+05:30",
    service_ends_at: "2027-04-01T10:00:00+05:30",
    package_code: "gold" as const,
  };
  beforeEach(() => actions.requestAssistance.mockReset());

  it("lets an eligible member ask once", async () => {
    render(<AssistanceCard assistance={{ included: true, can_request: true, available: true, requests: [] }} profileActive />);
    actions.requestAssistance.mockResolvedValue({ ok: true, data: request });
    await userEvent.type(screen.getByLabelText(/What would you like help with/), "A teacher in Thrissur");
    await userEvent.click(screen.getByRole("button", { name: "Ask for matchmaking assistance" }));
    expect(actions.requestAssistance).toHaveBeenCalledWith("A teacher in Thrissur");
  });

  it("never claims a matchmaker before one is assigned", () => {
    const { rerender } = render(
      <AssistanceCard assistance={{ included: true, can_request: true, available: true, requests: [request] }} profileActive />,
    );
    expect(screen.getByText("Awaiting assignment")).toBeTruthy();
    expect(screen.queryByText(/is your matchmaker/)).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    rerender(
      <AssistanceCard
        assistance={{
          included: true,
          can_request: true,
          available: true,
          requests: [{ ...request, status: "assigned", status_label: "Matchmaker assigned", assigned: true, matchmaker_name: "Lakshmi", assigned_at: "2026-10-28T10:00:00+05:30" }],
        }}
        profileActive
      />,
    );
    expect(screen.getByText(/Lakshmi is your matchmaker/)).toBeTruthy();
  });

  it("offers nothing when not included or unavailable", () => {
    const { rerender } = render(<AssistanceCard assistance={{ included: false, can_request: false, available: true, requests: [] }} profileActive />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Included with the Gold and Diamond memberships.")).toBeTruthy();
    rerender(<AssistanceCard assistance={{ included: true, can_request: true, available: false, requests: [] }} profileActive />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/currently unavailable/)).toBeTruthy();
  });
});

describe("VerificationCard", () => {
  beforeEach(() => actions.requestVerification.mockReset());

  it("offers the request only when the plan includes it", async () => {
    const { rerender } = render(
      <VerificationCard status="not_requested" note="" verifiedAt={null} eligible={false} profileActive />,
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Available with the Silver, Gold and Diamond memberships.")).toBeTruthy();

    rerender(<VerificationCard status="not_requested" note="" verifiedAt={null} eligible profileActive />);
    actions.requestVerification.mockResolvedValue({ ok: true, data: {} });
    await userEvent.click(screen.getByRole("button", { name: "Request verification" }));
    expect(actions.requestVerification).toHaveBeenCalledOnce();
  });

  it("never offers a request once verified or while one is waiting", () => {
    const { rerender } = render(
      <VerificationCard status="verified" note="" verifiedAt="2026-10-01T10:00:00+05:30" eligible profileActive />,
    );
    expect(screen.getByText("Verified")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<VerificationCard status="requested" note="" verifiedAt={null} eligible profileActive />);
    expect(screen.getByText("Awaiting verification")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows why verification was declined and the API's error", async () => {
    render(<VerificationCard status="declined" note="The ID photo was unreadable." verifiedAt={null} eligible profileActive />);
    expect(screen.getByText("The ID photo was unreadable.")).toBeTruthy();
    actions.requestVerification.mockResolvedValue({ ok: false, status: 403, message: "Not allowed.", fieldErrors: {} });
    await userEvent.click(screen.getByRole("button", { name: "Ask again" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Not allowed.");
  });
});
