import type { ProfileDetail } from "./types";

/** 175 → 5′9″ (175 cm). Matches the height labels in the partner search. */
export function formatHeight(cm: number): string {
  const inches = Math.round(cm / 2.54);
  return `${Math.floor(inches / 12)}′${inches % 12}″ (${cm} cm)`;
}

/** Feet and inches only, for compact places such as the summary line. */
export function formatHeightShort(cm: number): string {
  const inches = Math.round(cm / 2.54);
  return `${Math.floor(inches / 12)}′${inches % 12}″`;
}

/** "Kochi, Kerala": the most specific place the member made public, then the state. */
export function formatLocation({ city, district, state }: ProfileDetail["location"]): string {
  return [city ?? district, state].filter(Boolean).join(", ");
}

export function formatRange([min, max]: [number, number], format: (value: number) => string = String): string {
  return min === max ? format(min) : `${format(min)} – ${format(max)}`;
}
