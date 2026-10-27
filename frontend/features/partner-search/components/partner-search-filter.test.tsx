import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { describeFilters, filtersFromQuery } from "../schema";
import { PartnerSearchFilter } from "./partner-search-filter";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

beforeEach(() => router.push.mockReset());

const slider = (name: string) => screen.getByRole<HTMLInputElement>("slider", { name });
const group = (name: "Age" | "Height") => screen.getByRole("group", { name });
const move = (name: string, value: number) => fireEvent.change(slider(name), { target: { value: String(value) } });

/** The query string the form navigated to on submit. */
async function submit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Search profiles" }));
  expect(router.push).toHaveBeenCalledOnce();
  const url = new URL(router.push.mock.calls[0][0], "http://localhost");
  expect(url.pathname).toBe("/search");
  return url.searchParams.toString();
}

describe("age and height sliders", () => {
  it("start at the ends of their scales, meaning any age and any height", () => {
    render(<PartnerSearchFilter />);

    expect(slider("Minimum age").value).toBe("18");
    expect(slider("Maximum age").value).toBe("70");
    expect(slider("Minimum height").value).toBe("137");
    expect(slider("Maximum height").value).toBe("198");
    expect(within(group("Age")).getByText("Any")).toBeTruthy();
    expect(within(group("Height")).getByText("Any")).toBeTruthy();
    expect(slider("Minimum age").getAttribute("aria-valuetext")).toBe("No minimum");
    expect(slider("Maximum height").getAttribute("aria-valuetext")).toBe("No maximum");
    // The dropdowns they replace are gone.
    expect(screen.queryByRole("combobox", { name: /age|height/i })).toBeNull();
  });

  it("show each end of the range as it moves", () => {
    render(<PartnerSearchFilter />);

    move("Minimum age", 25);
    expect(within(group("Age")).getByText("From 25 yrs")).toBeTruthy();
    move("Maximum age", 40);
    expect(within(group("Age")).getByText("25 – 40 yrs")).toBeTruthy();
    expect(slider("Maximum age").getAttribute("aria-valuetext")).toBe("40 years");

    move("Maximum height", 170);
    expect(within(group("Height")).getByText("Up to 170 cm")).toBeTruthy();
    move("Minimum height", 150);
    expect(within(group("Height")).getByText("150 – 170 cm")).toBeTruthy();
    expect(slider("Minimum height").getAttribute("aria-valuetext")).toBe("150 centimetres");
  });

  it("never let the minimum pass the maximum, or the maximum drop below the minimum", () => {
    render(<PartnerSearchFilter />);

    move("Maximum age", 30);
    move("Minimum age", 50);
    expect(slider("Minimum age").value).toBe("30");
    expect(within(group("Age")).getByText("30 – 30 yrs")).toBeTruthy();

    move("Minimum height", 170);
    move("Maximum height", 140);
    expect(slider("Maximum height").value).toBe("170");
    expect(within(group("Height")).getByText("170 – 170 cm")).toBeTruthy();
  });

  it("are reachable from the keyboard, each thumb with its own name", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter />);

    await user.selectOptions(screen.getByRole("combobox", { name: "I am looking for a" }), "groom");
    await user.tab();
    expect(document.activeElement).toBe(slider("Minimum age"));
    await user.tab();
    expect(document.activeElement).toBe(slider("Maximum age"));
    await user.tab();
    expect(document.activeElement).toBe(slider("Minimum height"));
    await user.tab();
    expect(document.activeElement).toBe(slider("Maximum height"));
  });

  it("move the nearer thumb to a tap on the track", () => {
    render(<PartnerSearchFilter />);
    const area = slider("Minimum age").parentElement!;
    const track = area.firstElementChild as HTMLElement;
    // 18-70 over 520px: 10px a year.
    vi.spyOn(track, "getBoundingClientRect").mockReturnValue({ left: 0, width: 520 } as DOMRect);
    // jsdom has no PointerEvent; a MouseEvent of that type carries the position.
    const tap = (clientX: number) =>
      fireEvent(area, new MouseEvent("pointerdown", { bubbles: true, clientX, button: 0 }));

    tap(470); // 65: nearer the maximum
    expect(slider("Maximum age").value).toBe("65");
    tap(120); // 30: nearer the minimum
    expect(slider("Minimum age").value).toBe("30");
    expect(within(group("Age")).getByText("30 – 65 yrs")).toBeTruthy();
  });
});

describe("bride or groom", () => {
  it("is a dropdown that must be chosen before searching", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter />);
    const lookingFor = screen.getByRole<HTMLSelectElement>("combobox", { name: "I am looking for a" });
    expect(lookingFor.value).toBe("");
    expect([...lookingFor.options].map((option) => option.text)).toEqual(["Bride or groom", "Bride", "Groom"]);
    expect(screen.queryByRole("radio")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Search profiles" }));
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.getByText("Choose bride or groom.")).toBeTruthy();
    expect(lookingFor.getAttribute("aria-invalid")).toBe("true");

    await user.selectOptions(lookingFor, "bride");
    expect(await submit(user)).toBe("gender=female");
  });

  it("starts from the URL and is cleared by Clear all", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter initialValues={filtersFromQuery({ gender: "male" })} />);
    const lookingFor = screen.getByRole<HTMLSelectElement>("combobox", { name: "I am looking for a" });
    expect(lookingFor.value).toBe("groom");

    await user.click(screen.getByRole("button", { name: "Clear all" }));
    expect(lookingFor.value).toBe("");
  });
});

describe("searching with the sliders", () => {
  it("sends the API's age and height parameters with the other filters", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter />);

    await user.selectOptions(screen.getByRole("combobox", { name: "I am looking for a" }), "bride");
    move("Minimum age", 25);
    move("Maximum age", 32);
    move("Minimum height", 150);
    move("Maximum height", 170);
    await user.selectOptions(screen.getByRole("combobox", { name: "Religion" }), "christian");
    await user.selectOptions(screen.getByRole("combobox", { name: "Community" }), "latin-catholic");
    await user.selectOptions(screen.getByRole("combobox", { name: "Location" }), "ernakulam");

    expect(await submit(user)).toBe(
      "gender=female&age_min=25&age_max=32&height_min=150&height_max=170&religion=christian&caste=latin-catholic&location=ernakulam",
    );
  });

  it("leave out an end of the range that sits at the end of the scale", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter />);

    await user.selectOptions(screen.getByRole("combobox", { name: "I am looking for a" }), "groom");
    move("Minimum age", 30);
    move("Minimum age", 18); // back to the start: no minimum
    move("Maximum height", 175);

    expect(await submit(user)).toBe("gender=male&height_max=175");
  });

  it("start from the filters in the URL", () => {
    const initialValues = filtersFromQuery({ gender: "female", age_min: "26", height_max: "165" });
    render(<PartnerSearchFilter initialValues={initialValues} />);

    expect(slider("Minimum age").value).toBe("26");
    expect(slider("Maximum age").value).toBe("70");
    expect(slider("Maximum height").value).toBe("165");
    expect(within(group("Age")).getByText("From 26 yrs")).toBeTruthy();
    expect(within(group("Height")).getByText("Up to 165 cm")).toBeTruthy();
  });

  it("go back to any age and any height on Clear all, and nothing of them is sent", async () => {
    const user = userEvent.setup();
    render(<PartnerSearchFilter initialValues={{ lookingFor: "groom", ageMin: "28", ageMax: "35", heightMin: "160" }} />);

    await user.click(screen.getByRole("button", { name: "Clear all" }));
    expect(slider("Minimum age").value).toBe("18");
    expect(slider("Maximum age").value).toBe("70");
    expect(slider("Minimum height").value).toBe("137");
    expect(within(group("Age")).getByText("Any")).toBeTruthy();
    expect(within(group("Height")).getByText("Any")).toBeTruthy();

    await user.selectOptions(screen.getByRole("combobox", { name: "I am looking for a" }), "groom");
    expect(await submit(user)).toBe("gender=male");
  });
});

describe("range filters in the URL", () => {
  it("drop a range whose minimum is above its maximum", () => {
    expect(filtersFromQuery({ age_min: "40", age_max: "30", height_min: "150", height_max: "170" })).toEqual({
      heightMin: "150",
      heightMax: "170",
    });
    expect(filtersFromQuery({ height_min: "180", height_max: "160" })).toEqual({});
  });

  it("are summarised in centimetres", () => {
    expect(describeFilters({ ageMin: "25", ageMax: "30", heightMin: "152" })).toEqual([
      "Age 25 – 30",
      "Height from 152 cm",
    ]);
    expect(describeFilters({ heightMin: "150", heightMax: "170" })).toEqual(["Height 150 – 170 cm"]);
  });
});
