import { connection } from "next/server";

import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { getApiHealth } from "../api";

/** Server component that checks the backend health endpoint at request time. */
export async function ApiStatus() {
  await connection();

  let healthy = false;
  let message: string;
  try {
    const health = await getApiHealth();
    healthy = health.status === "ok";
    message = healthy ? `Connected to ${health.service} (${health.api_version}).` : "The API reported a problem.";
  } catch (error) {
    message =
      error instanceof ApiError && error.isNetworkError
        ? "The API could not be reached. Is the backend running?"
        : "The API returned an unexpected response.";
  }

  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-3 rounded-xl border p-4",
        healthy ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5",
      )}
    >
      <span aria-hidden="true" className={cn("h-3 w-3 rounded-full", healthy ? "bg-success" : "bg-danger")} />
      <p className="text-sm">
        <span className="font-semibold">{healthy ? "Operational" : "Unavailable"}</span>
        <span className="text-ink-muted"> &mdash; {message}</span>
      </p>
    </div>
  );
}
