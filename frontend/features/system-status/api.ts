import { api } from "@/lib/api/client";
import type { HealthResponse } from "@/types/api";

export function getApiHealth() {
  return api.get<HealthResponse>("/health/", { timeoutMs: 5_000 });
}
