import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { communitiesForReligions } from "../profile-options";
import type { MatchCard } from "../types";
import { MemberGrid } from "./member-grid";

vi.mock("../actions", () => ({ addToShortlist: vi.fn(), removeFromShortlist: vi.fn() }));

function card(overrides: Partial<MatchCard> = {}): MatchCard {
  return {
    profile_code: "MM100001",
    display_name: "Anu Mohan",
    gender: "female",
    age: 26,
    height_cm: 160,
    marital_status: "Never married",
    religion: "Hindu",
    community: "Nair",
    education: "B.Tech",
    occupation: "Engineer",
    location: { city: "Kochi", district: "Ernakulam", state: "Kerala", country: "India" },
    photo: null,
    photos_hidden: false,
    shortlisted: false,
    match: {
      score: 86,
      reasons: [
        "Matches your age preference (24–28)",
        "Matches your religion preference",
        "Lives in or comes from a place you prefer",
        "Matches your education preference",
      ],
      not_stated: [],
      mutual: true,
    },
    ...overrides,
  };
}

describe("MemberGrid with match information", () => {
  it("shows the score, the mutual badge and up to three reasons", () => {
    render(<MemberGrid members={[card()]} />);
    expect(screen.getByText("86% match")).toBeTruthy();
    expect(screen.getByText("Mutual")).toBeTruthy();
    const reasons = screen.getByText("Why it's a match").parentElement!;
    expect(within(reasons).getAllByRole("listitem")).toHaveLength(3);
    expect(within(reasons).getByText("and 1 more")).toBeTruthy();
    // Screen readers get the score in the card text, since the photo link is hidden from them.
    expect(screen.getByText(/86% match with your partner preferences\. Mutual: you also meet/)).toBeTruthy();
  });

  it("links to the right profile", () => {
    render(<MemberGrid members={[card()]} />);
    expect(screen.getByRole("link", { name: "Anu Mohan" }).getAttribute("href")).toContain("MM100001");
  });

  it("shows no score when the member has no preferences, and nothing invented", () => {
    render(<MemberGrid members={[card({ match: { score: null, reasons: [], not_stated: [], mutual: false } })]} />);
    expect(screen.queryByText(/% match/)).toBeNull();
    expect(screen.queryByText("Mutual")).toBeNull();
    expect(screen.queryByText("Why it's a match")).toBeNull();
  });

  it("shows only the score badge on compact cards", () => {
    render(<MemberGrid members={[card()]} compact />);
    expect(screen.getByText("86% match")).toBeTruthy();
    expect(screen.queryByText("Why it's a match")).toBeNull();
  });

  it("works for cards without match information (interests, shortlist)", () => {
    const { match, ...plain } = card();
    void match;
    render(<MemberGrid members={[plain]} />);
    expect(screen.getByText("Anu Mohan")).toBeTruthy();
    expect(screen.queryByText(/% match/)).toBeNull();
  });
});

describe("communitiesForReligions", () => {
  it("offers the chosen religions' communities, or all of them", () => {
    const christian = communitiesForReligions(["christian"]).map((option) => option.value);
    expect(christian).toContain("syro-malabar");
    expect(christian).not.toContain("nair");
    const all = communitiesForReligions([]).map((option) => option.value);
    expect(all).toEqual(expect.arrayContaining(["nair", "syro-malabar", "sunni"]));
  });
});
