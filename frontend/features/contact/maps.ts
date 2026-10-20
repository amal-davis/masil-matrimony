/**
 * Google Maps links for an address. Both are keyless: the embed uses the
 * public "output=embed" URL, so no Maps API key is needed or exposed.
 */
export function mapsSearchUrl(address: readonly string[]): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address.join(", "))}`;
}

export function mapsEmbedUrl(address: readonly string[]): string {
  return `https://www.google.com/maps?q=${encodeURIComponent(address.join(", "))}&output=embed`;
}
