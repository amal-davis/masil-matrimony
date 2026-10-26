import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHighlightedProfiles } from "../api";
import { HighlightedProfiles, HighlightedProfilesSkeleton } from "./highlighted-profiles";

const client = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/lib/api/client", () => ({ api: client }));
// next/image needs Next's runtime; a plain <img> keeps the test about the section itself.
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

const anjali = {
  profile_code: "MM482913",
  given_name: "Anjali",
  gender: "female",
  age: 26,
  education: "M.Sc",
  location: { city: "Kochi", district: "Ernakulam", state: "Kerala" },
  photo: { url: "http://127.0.0.1:8000/api/v1/profiles/photo-files/abc/", width: 800, height: 1000 },
};
const rahul = { ...anjali, profile_code: "MM100200", given_name: "Rahul", gender: "male", city: "", photo: null,
  location: { city: "", district: "Thrissur", state: "Kerala" } };

async function renderSection() {
  const element = await HighlightedProfiles();
  return element ? render(element) : null;
}

beforeEach(() => {
  client.get.mockReset();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("getHighlightedProfiles", () => {
  it("asks the API every time, uncached, and maps the public fields", async () => {
    client.get.mockResolvedValue([anjali]);
    const result = await getHighlightedProfiles();
    expect(client.get).toHaveBeenCalledWith("/profiles/highlighted/?limit=12", { cache: "no-store" });
    expect(result).toEqual({
      source: "api",
      profiles: [{
        id: "MM482913", profileCode: "MM482913", displayName: "Anjali", gender: "female", age: 26, education: "M.Sc",
        location: { city: "Kochi", district: "Ernakulam", state: "Kerala" }, photo: anjali.photo,
      }],
    });
  });

  it("reflects a removed highlight on the next call", async () => {
    client.get.mockResolvedValueOnce([anjali, rahul]).mockResolvedValueOnce([rahul]);
    expect((await getHighlightedProfiles()).profiles).toHaveLength(2);
    expect((await getHighlightedProfiles()).profiles.map((p) => p.profileCode)).toEqual(["MM100200"]);
  });
});

describe("HighlightedProfiles", () => {
  it("renders the API's profiles as cards linking to their profile pages", async () => {
    client.get.mockResolvedValue([anjali, rahul]);
    await renderSection();
    expect(screen.getByRole("heading", { name: "Highlighted Profiles" })).toBeTruthy();
    expect(screen.getByText("Anjali")).toBeTruthy();
    expect(screen.getByAltText("Photo of Anjali").getAttribute("src")).toBe(anjali.photo.url);
    const links = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(links).toEqual(expect.arrayContaining(["/profile/MM482913", "/profile/MM100200"]));
    expect(screen.queryByText(/Sample profiles/)).toBeNull();
  });

  it("shows an empty state when nothing is highlighted, and never sample profiles", async () => {
    client.get.mockResolvedValue([]);
    await renderSection();
    expect(screen.getByText(/Featured member profiles will appear here soon/)).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("leaves the section out when the API fails, without showing error details", async () => {
    client.get.mockRejectedValue(new Error("Internal: database password wrong"));
    const rendered = await renderSection();
    expect(rendered).toBeNull();
    expect(document.body.textContent).not.toContain("database");
  });

  it("has a loading placeholder", () => {
    const { container } = render(<HighlightedProfilesSkeleton />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });
});
