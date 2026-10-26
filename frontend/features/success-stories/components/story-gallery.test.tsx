import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getSuccessStories, getSuccessStory } from "../api";
import { StoryGallery } from "./story-gallery";

// The real client checks .env.local on import; this stands in for it, with the same ApiError shape.
const { client, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
    get isNetworkError() {
      return this.status === 0;
    }
  }
  return { client: { get: vi.fn() }, ApiError };
});
vi.mock("@/lib/api/client", () => ({ api: client, ApiError }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

const card = {
  id: "0b7c…",
  slug: "a-beautiful-beginning",
  title: "A Beautiful Beginning",
  couple_names: "Anu & Rahul",
  summary: "Two families from Thrissur found each other.",
  image: { url: "http://127.0.0.1:8000/api/v1/success-stories/images/abc/?v=1", width: 1200, height: 900, alt: "Anu and Rahul" },
  published_at: "2026-10-01T10:00:00Z",
};
const page = (results: unknown[], extra = {}) => ({ count: results.length, next: null, previous: null, results, ...extra });

async function renderGallery(props = {}) {
  return render(await StoryGallery(props));
}

beforeEach(() => {
  client.get.mockReset();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("StoryGallery", () => {
  it("renders the API's stories with the short description and a Read more link to the story", async () => {
    client.get.mockResolvedValue(page([card]));
    await renderGallery();
    expect(client.get).toHaveBeenCalledWith("/success-stories/", { cache: "no-store" });
    const item = screen.getByRole("listitem");
    expect(within(item).getByText("Two families from Thrissur found each other.")).toBeTruthy();
    expect(within(item).getByText("Read more")).toBeTruthy();
    // One link per card (the title, stretched over the card): no nested interactive elements.
    const links = within(item).getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/success-stories/a-beautiful-beginning");
    expect(links[0].textContent).toBe("Anu & Rahul");
    expect(within(item).getByAltText("Anu and Rahul").getAttribute("src")).toBe(card.image.url);
    expect(screen.queryByText(/Sample/)).toBeNull();
  });

  it("shows an empty state with no stories, and never sample stories", async () => {
    client.get.mockResolvedValue(page([]));
    await renderGallery();
    expect(screen.getByText(/success-story gallery is growing/)).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("shows an error with a retry, not made-up stories, when the API fails", async () => {
    client.get.mockRejectedValue(new ApiError(0, "Unable to reach the server."));
    await renderGallery();
    expect(screen.getByText(/couldn't load the success stories/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("pages through stories", async () => {
    client.get.mockResolvedValue(page([card], { count: 25, next: "http://x/?page=3", previous: "http://x/" }));
    await renderGallery({ page: 2 });
    expect(client.get).toHaveBeenCalledWith("/success-stories/?page=2", { cache: "no-store" });
    expect(screen.getByRole("link", { name: "Previous stories" }).getAttribute("href")).toBe("/success-stories");
    expect(screen.getByRole("link", { name: "More stories" }).getAttribute("href")).toBe("/success-stories?page=3");
  });

  it("treats a page past the end as empty", async () => {
    client.get.mockRejectedValue(new ApiError(404, "Invalid page."));
    await renderGallery({ page: 9 });
    expect(screen.getByRole("link", { name: "Back to the first page" })).toBeTruthy();
  });
});

describe("getSuccessStory", () => {
  it("returns the full story's paragraphs", async () => {
    client.get.mockResolvedValue({ ...card, paragraphs: ["First.", "Second."] });
    const found = await getSuccessStory("a-beautiful-beginning");
    expect(client.get).toHaveBeenCalledWith("/success-stories/a-beautiful-beginning/", { cache: "no-store" });
    expect(found?.story).toMatchObject({ heading: "A Beautiful Beginning", couple: "Anu & Rahul", paragraphs: ["First.", "Second."] });
  });

  it("is null for drafts and unknown slugs, without asking for invalid ones", async () => {
    client.get.mockRejectedValue(new ApiError(404, "Story not found."));
    expect(await getSuccessStory("a-draft-story")).toBeNull();
    client.get.mockClear();
    expect(await getSuccessStory("../../etc/passwd")).toBeNull();
    expect(client.get).not.toHaveBeenCalled();
  });

  it("throws on other errors so the page can offer a retry", async () => {
    client.get.mockRejectedValue(new ApiError(500, "Server error"));
    await expect(getSuccessStory("a-beautiful-beginning")).rejects.toThrow();
  });
});

describe("getSuccessStories", () => {
  it("maps the card fields", async () => {
    client.get.mockResolvedValue(page([{ ...card, couple_names: "", image: null }]));
    const result = await getSuccessStories();
    expect(result.stories[0]).toMatchObject({ slug: card.slug, heading: card.title, couple: undefined, photo: null });
    expect(result.source).toBe("api");
  });
});
