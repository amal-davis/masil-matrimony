import { accessToken } from "@/features/auth/session";
import type { MemberCard, Paginated } from "@/features/dashboard/types";
import { api, ApiError } from "@/lib/api/client";

/** One result of GET /profiles/search/ (backend/apps/profiles/search.py). */
export type SearchResultCard = MemberCard & { shortlisted: boolean };

export type SearchOutcome =
  | { kind: "results"; page: Paginated<SearchResultCard>; searchingFor: "male" | "female" }
  /** Profiles are for signed-in members only, so visitors are asked to log in. */
  | { kind: "signed_out" }
  /** Signed in, but the member hasn't created their own profile yet. */
  | { kind: "no_profile" }
  /** The API refused a filter, e.g. a search for the member's own gender: field → message. */
  | { kind: "invalid"; errors: Record<string, string> }
  /** The page number is past the last page. */
  | { kind: "past_end" };

/**
 * Search approved profiles as the signed-in member, so the API applies their
 * visibility rules. `query` is the search page's own query string (its parameter
 * names are the API's). Read on every request: a newly approved profile shows at
 * once. Throws when the API can't be reached, so the page shows an error, never
 * made-up results. Reads the session cookie: call inside <Suspense>.
 */
export async function searchProfiles(query: URLSearchParams): Promise<SearchOutcome> {
  const token = await accessToken();
  if (!token) return { kind: "signed_out" };
  const search = query.toString();
  try {
    const data = await api.get<Paginated<SearchResultCard> & { searching_for: "male" | "female" }>(
      `/profiles/search/${search ? `?${search}` : ""}`,
      { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
    );
    const { searching_for: searchingFor, ...page } = data;
    return { kind: "results", page, searchingFor };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) return { kind: "signed_out" };
      if (error.status === 403 && error.body?.code === "no_profile") return { kind: "no_profile" };
      // The paginator answers a page past the end with 404.
      if (error.status === 404 && query.has("page")) return { kind: "past_end" };
      if (error.status === 400 && error.body) return { kind: "invalid", errors: fieldMessages(error.body) };
    }
    throw error;
  }
}

function fieldMessages(body: object): Record<string, string> {
  const messages: Record<string, string> = {};
  for (const [field, value] of Object.entries(body)) {
    const text = Array.isArray(value) ? value[0] : value;
    if (typeof text === "string") messages[field] = text;
  }
  return messages;
}
