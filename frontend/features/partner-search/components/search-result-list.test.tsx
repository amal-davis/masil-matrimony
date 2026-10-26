import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { filtersFromQuery, filtersToQuery } from "../schema";
import { SearchResultList } from "./search-result-list";

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
vi.mock("@/features/dashboard/actions", () => ({ addToShortlist: vi.fn(), removeFromShortlist: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const card = {
  profile_code: "MM706381",
  display_name: "Anu",
  gender: "female",
  age: 27,
  height_cm: 160,
  marital_status: "Never married",
  religion: "Christian",
  community: "Syro-Malabar Catholic",
  education: "B.Tech",
  occupation: "Engineer",
  location: { city: "Thrissur", district: "Thrissur", state: "Kerala", country: "India" },
  photo: null,
  photos_hidden: false,
  shortlisted: false,
};
const page = (results: unknown[], count = results.length) => ({
  count,
  next: null,
  previous: null,
  results,
  searching_for: "female",
});

async function renderList(query: Record<string, string | string[]> = {}) {
  return render(await SearchResultList({ query }));
}

beforeEach(() => {
  client.get.mockReset();
  session.token = "token";
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("SearchResultList", () => {
  it("sends the chosen filters to the search API as the signed-in member", async () => {
    client.get.mockResolvedValue(page([card]));
    await renderList({ gender: "female", religion: "christian", location: "thrissur", color: "blue", age_min: " " });
    const [path, options] = client.get.mock.calls[0];
    expect(path).toBe("/profiles/search/?gender=female&religion=christian&location=thrissur");
    expect(options).toEqual({ headers: { Authorization: "Bearer token" }, cache: "no-store" });
  });

  it("shows the count and links each card to that profile", async () => {
    client.get.mockResolvedValue(page([card]));
    await renderList();
    expect(screen.getByRole("status").textContent).toBe("1 profile found");
    const links = screen.getAllByRole("link").filter((link) => link.getAttribute("href") === "/profile/MM706381");
    expect(links.length).toBeGreaterThan(0);
  });

  it("says so when no profiles match, without sample profiles", async () => {
    client.get.mockResolvedValue(page([]));
    await renderList({ religion: "muslim" });
    expect(screen.getByText("No profiles match your search")).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("shows an error with a retry when the API fails", async () => {
    client.get.mockRejectedValue(new ApiError(0, "Unable to reach the server."));
    await renderList();
    expect(screen.getByText("We couldn't search profiles just now")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("asks visitors to log in, keeping the search, without calling the API", async () => {
    session.token = undefined;
    await renderList({ religion: "hindu" });
    expect(client.get).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Log in to search" }).getAttribute("href")).toBe(
      `/login?next=${encodeURIComponent("/search?religion=hindu")}`,
    );
  });

  it("shows the API's message for a refused filter", async () => {
    client.get.mockRejectedValue(new ApiError(400, "Bad request", { gender: ["Search shows brides for your profile."] }));
    await renderList({ gender: "male" });
    expect(screen.getByRole("alert").textContent).toContain("Search shows brides for your profile.");
  });

  it("asks members without a profile to create one", async () => {
    client.get.mockRejectedValue(new ApiError(403, "No profile", { code: "no_profile" }));
    await renderList();
    expect(screen.getByText("Create your profile first")).toBeTruthy();
  });

  it("pages keep the filters", async () => {
    client.get.mockResolvedValue(page([card], 45));
    await renderList({ religion: "hindu", page: "2" });
    expect(client.get.mock.calls[0][0]).toBe("/profiles/search/?religion=hindu&page=2");
    const next = screen.getAllByRole("link").find((link) => link.getAttribute("href")?.includes("page=3"));
    expect(next?.getAttribute("href")).toBe("/search?religion=hindu&page=3");
  });
});

describe("search form query", () => {
  it("uses the API's parameter names and starts a new search on page 1", () => {
    const query = filtersToQuery({
      lookingFor: "bride",
      ageMin: "25",
      ageMax: "30",
      heightMin: "",
      heightMax: "",
      religion: "christian",
      community: "syro-malabar",
      location: "thrissur",
      maritalStatus: "",
      motherTongue: "malayalam",
      education: "B.Tech",
      occupation: "",
      profileId: "mm706381",
    });
    expect(query.toString()).toBe(
      "gender=female&age_min=25&age_max=30&religion=christian&caste=syro-malabar&location=thrissur&mother_tongue=malayalam&education=B.Tech&profile_id=mm706381",
    );
    expect(query.has("page")).toBe(false);
  });

  it("reads the new text filters back from the URL and drops invalid ones", () => {
    expect(filtersFromQuery({ education: "MBBS", profile_id: "MM706381" })).toMatchObject({
      education: "MBBS",
      profileId: "MM706381",
    });
    expect(filtersFromQuery({ profile_id: "not-an-id" }).profileId).toBeUndefined();
  });
});
