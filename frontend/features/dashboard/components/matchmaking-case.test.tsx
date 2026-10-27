import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardLoading from "@/app/(dashboard)/dashboard/loading";

import type { AssistanceCase, ContactExchangeItem, MemberCard } from "../types";
import { AssistanceCard } from "./assistance-card";
import { ContactExchangeCard } from "./contact-exchange-card";
import { MatchmakingCase } from "./matchmaking-case";

const actions = vi.hoisted(() => ({
  requestAssistance: vi.fn(),
  respondToSuggestion: vi.fn(),
  decideContactExchange: vi.fn(),
  updateRequirements: vi.fn(),
  requestConsultation: vi.fn(),
  consultationAction: vi.fn(),
  addFamilyContact: vi.fn(),
  decideFamilyContact: vi.fn(),
}));
vi.mock("../actions", () => actions);

const bride: MemberCard = {
  profile_code: "MM100001",
  display_name: "Meera",
  gender: "female",
  age: 26,
  height_cm: 160,
  location: { city: "", district: "Thrissur", state: "Kerala" },
  religion: "hindu",
  community: "nair",
  education: "B.Tech",
  occupation: "Engineer",
  photo: null,
  verified: false,
} as unknown as MemberCard;

const waiting: AssistanceCase = {
  id: "00000000-0000-4000-a000-000000000009",
  kind: "service",
  status: "requested",
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
  service_starts_at: "2026-10-27T10:00:00+05:30",
  service_ends_at: "2027-01-27T10:00:00+05:30",
  package_code: "platinum",
  features: { contact_exchange: true, consultations: false, family: false },
  requirements: "",
  service_plan: "",
  next_steps: "",
  consultations: [],
  family: [],
  updates: [],
  follow_ups: [],
  suggestions: [],
  exchanges: [],
};

const exchange: ContactExchangeItem = {
  id: "00000000-0000-4000-a000-000000000010",
  status: "pending",
  status_label: "Pending consent",
  purpose: "Both families asked to talk.",
  statement: "Share my mobile number with Meera (MM100001), and see theirs. Purpose: Both families asked to talk.",
  shares: "mobile number",
  my_decision: "pending",
  created_at: "2026-10-28T10:00:00+05:30",
  shared_at: null,
  profile: bride,
  phone_number: null,
};

beforeEach(() => Object.values(actions).forEach((action) => action.mockReset()));

describe("MatchmakingCase", () => {
  it("is honest while no matchmaker is assigned", () => {
    render(<MatchmakingCase item={waiting} />);
    expect(screen.getByText("Awaiting assignment")).toBeTruthy();
    expect(screen.getByText("Not assigned yet")).toBeTruthy();
    expect(screen.getByText(/awaiting assignment\. We'll let you know/)).toBeTruthy();
    expect(screen.getByText("No suggestions yet")).toBeTruthy();
  });

  it("shows the assigned matchmaker, updates, follow-ups and suggestions from the API", async () => {
    render(
      <MatchmakingCase
        item={{
          ...waiting,
          status: "in_progress",
          status_label: "In progress",
          assigned: true,
          matchmaker_name: "Lakshmi",
          updates: [{ body: "We shortlisted three profiles.", created_at: "2026-10-29T10:00:00+05:30" }],
          follow_ups: [
            { action: "Review suggestions with you", due_on: "2026-11-02", status: "scheduled", status_label: "Scheduled", awaiting_member: true },
          ],
          suggestions: [{ profile: bride, status: "shared", shared_at: "2026-10-29T10:00:00+05:30", response: "pending" }],
        }}
      />,
    );
    expect(screen.getByText("Lakshmi")).toBeTruthy();
    expect(screen.getByText("We shortlisted three profiles.")).toBeTruthy();
    expect(screen.getByText(/waiting for your response/)).toBeTruthy();
    actions.respondToSuggestion.mockResolvedValue({ ok: true, data: { response: "interested" } });
    await userEvent.click(screen.getByRole("button", { name: "Interested" }));
    expect(actions.respondToSuggestion).toHaveBeenCalledWith(waiting.id, "MM100001", "interested");
  });

  it("says when the service period has ended or the service is unavailable", () => {
    const { rerender } = render(<MatchmakingCase item={{ ...waiting, status: "assigned", service_active: false }} />);
    expect(screen.getByText(/service period has ended/)).toBeTruthy();
    rerender(<MatchmakingCase item={{ ...waiting, status: "unavailable", status_label: "Unavailable", is_open: false }} />);
    expect(screen.getByText(/couldn't offer matchmaking assistance/)).toBeTruthy();
  });
});

describe("ContactExchangeCard", () => {
  it("keeps the number hidden and asks for this member's own consent", async () => {
    render(<ContactExchangeCard exchange={exchange} />);
    expect(screen.getByText(/Numbers stay hidden until both of you consent/)).toBeTruthy();
    expect(screen.getByText(exchange.statement)).toBeTruthy();
    actions.decideContactExchange.mockResolvedValue({ ok: false, status: 409, message: "This request is no longer open.", fieldErrors: {} });
    await userEvent.click(screen.getByRole("button", { name: "I consent" }));
    expect(actions.decideContactExchange).toHaveBeenCalledWith(exchange.id, "grant");
    expect((await screen.findByRole("alert")).textContent).toBe("This request is no longer open.");
  });

  it("offers withdrawal after consenting, and shows the number only when the API sends it", () => {
    const { rerender } = render(<ContactExchangeCard exchange={{ ...exchange, my_decision: "granted" }} />);
    expect(screen.getByRole("button", { name: "Withdraw consent" })).toBeTruthy();
    rerender(
      <ContactExchangeCard
        exchange={{ ...exchange, status: "shared", status_label: "Shared", my_decision: "granted", phone_number: "+919800000001" }}
      />,
    );
    expect(screen.getByRole("link", { name: "+919800000001" }).getAttribute("href")).toBe("tel:+919800000001");
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<ContactExchangeCard exchange={{ ...exchange, status: "declined", status_label: "Declined", my_decision: "declined" }} />);
    expect(screen.getByText(/No numbers were shared/)).toBeTruthy();
  });
});

describe("Platinum on the membership page", () => {
  it("links to the service case and offers no request form", () => {
    render(
      <AssistanceCard
        assistance={{ included: true, can_request: false, available: true, requests: [waiting] }}
        profileActive
      />,
    );
    expect(screen.getByRole("link", { name: "Open your matchmaking service" }).getAttribute("href")).toBe("/dashboard/matchmaking");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText(/Included with the Gold and Diamond/)).toBeNull();
  });
});

const royal: AssistanceCase = {
  ...waiting,
  package_code: "royal",
  status: "consult_requested",
  status_label: "Consultation requested",
  assigned: true,
  matchmaker_name: "Devika",
  features: { contact_exchange: true, consultations: true, family: true },
  requirements: "A doctor in Kerala.",
  service_plan: "Focus on Kochi families.",
  next_steps: "Review five profiles.",
  consultations: [
    {
      id: "00000000-0000-4000-a000-000000000020",
      status: "proposed",
      status_label: "Time proposed, awaiting your confirmation",
      member_note: "Weekends",
      location_provided: true,
      scheduled_for: "2026-11-07T11:00:00+05:30",
      confirmed_at: null,
      completed_at: null,
      message: "Saturday 11 am?",
      requested_at: "2026-10-28T10:00:00+05:30",
    },
  ],
  family: [
    {
      id: "00000000-0000-4000-a000-000000000030",
      name: "Suresh",
      relationship: "Father",
      phone_hint: "•••• 2222",
      purpose: "Discuss suggested profiles.",
      permission: "granted",
      permission_label: "Permitted",
      statement: "I permit my Massil Matrimony matchmaker to contact Suresh (Father) for this purpose only.",
      granted_at: "2026-10-28T10:00:00+05:30",
      withdrawn_at: null,
      actions: [{ action: "Called to introduce the service", created_at: "2026-10-29T10:00:00+05:30" }],
    },
  ],
  suggestions: [{ profile: null, status: "no_longer_available", shared_at: "2026-10-29T10:00:00+05:30", response: "pending" }],
};

describe("Royal service", () => {
  it("shows the plan apart from the member's own requirements, and lets them update theirs", async () => {
    render(<MatchmakingCase item={royal} />);
    expect(screen.getByText("Focus on Kochi families.")).toBeTruthy();
    expect(screen.getByText("Review five profiles.")).toBeTruthy();
    const box = screen.getByLabelText("Your requirements, in your own words") as HTMLTextAreaElement;
    expect(box.value).toBe("A doctor in Kerala.");
    actions.updateRequirements.mockResolvedValue({ ok: true, data: {} });
    await userEvent.type(box, " Vegetarian.");
    await userEvent.click(screen.getByRole("button", { name: "Save requirements" }));
    expect(actions.updateRequirements).toHaveBeenCalledWith(royal.id, "A doctor in Kerala. Vegetarian.");
  });

  it("schedules a consultation only when the member confirms the proposed time", async () => {
    render(<MatchmakingCase item={royal} />);
    expect(screen.getByText("Time proposed, awaiting your confirmation")).toBeTruthy();
    expect(screen.getByText("Visit address given to your matchmaker.")).toBeTruthy();
    expect(screen.queryByLabelText(/Address for the visit/)).toBeNull(); // one open consultation at a time
    actions.consultationAction.mockResolvedValue({ ok: true, data: {} });
    await userEvent.click(screen.getByRole("button", { name: "Confirm this time" }));
    expect(actions.consultationAction).toHaveBeenCalledWith(royal.id, royal.consultations[0].id, "confirm");
  });

  it("asks for a consultation with an optional address that is never shown back", async () => {
    render(<MatchmakingCase item={{ ...royal, consultations: [] }} />);
    actions.requestConsultation.mockResolvedValue({ ok: true, data: {} });
    await userEvent.type(screen.getByLabelText(/Address for the visit/), "12 Lotus Gardens");
    await userEvent.click(screen.getByRole("button", { name: "Request a consultation" }));
    expect(actions.requestConsultation).toHaveBeenCalledWith(royal.id, "", "12 Lotus Gardens");
  });

  it("coordinates with family only with permission, which can be withdrawn", async () => {
    render(<MatchmakingCase item={royal} />);
    expect(screen.getByText("Called to introduce the service", { exact: false })).toBeTruthy();
    expect(screen.queryByText(/9811112222/)).toBeNull();
    actions.decideFamilyContact.mockResolvedValue({ ok: true, data: {} });
    await userEvent.click(screen.getByRole("button", { name: "Withdraw permission" }));
    expect(actions.decideFamilyContact).toHaveBeenCalledWith(royal.id, royal.family[0].id, "withdraw");
    const give = screen.getAllByRole("button", { name: "Give permission" }).at(-1) as HTMLButtonElement;
    expect(give.disabled).toBe(true); // the permission box must be ticked
  });

  it("shows a curated profile that is no longer visible without its details", () => {
    render(<MatchmakingCase item={royal} />);
    expect(screen.getByText("A profile your matchmaker suggested is no longer available.")).toBeTruthy();
  });

  it("keeps Royal sections off other cases", () => {
    render(<MatchmakingCase item={waiting} />);
    expect(screen.queryByText("At-home consultations")).toBeNull();
    expect(screen.queryByText("Family coordination")).toBeNull();
  });
});

describe("loading", () => {
  it("shows the dashboard loading state", () => {
    render(<DashboardLoading />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeTruthy();
  });
});
