import { getApiBaseUrl } from "@/lib/config";
import type { ApiErrorBody } from "@/types/api";

const DEFAULT_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, message: string, body: ApiErrorBody | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  /** True when the request never reached the API (network failure or timeout). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

type RequestOptions = Omit<RequestInit, "body" | "method"> & {
  body?: unknown;
  timeoutMs?: number;
};

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (response.status === 204 || !contentType.includes("application/json")) {
    return null;
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeoutMs = DEFAULT_TIMEOUT_MS, headers, signal, ...init } = options;
  const url = `${getApiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Send cookies to the API (needed for cookie-based browser sessions).
      credentials: init.credentials ?? "include",
      signal: signal ?? AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new ApiError(0, timedOut ? "The server took too long to respond." : "Unable to reach the server.");
  }

  const data = await parseBody(response);

  if (!response.ok) {
    const errorBody = (data as ApiErrorBody | null) ?? null;
    const message =
      typeof errorBody?.detail === "string" ? errorBody.detail : `Request failed (${response.status}).`;
    throw new ApiError(response.status, message, errorBody);
  }

  return data as T;
}

/** Centralised client for the Django REST API. Paths are relative to /api/v1. */
export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "body">) => request<T>("GET", path, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, { ...options, body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, { ...options, body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, { ...options, body }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, options),
};
