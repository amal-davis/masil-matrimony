/** Shapes shared with the Django REST API (/api/v1/). */

export interface HealthResponse {
  status: "ok" | "unavailable";
  service: string;
  api_version: string;
}

/** DRF error body: `detail` for general errors, field names for validation errors. */
export interface ApiErrorBody {
  detail?: string;
  [field: string]: unknown;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
