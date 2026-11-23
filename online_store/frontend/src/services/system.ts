import { apiRequest } from "@/lib/api-client";

export interface ReadinessStatus {
  status: "ok" | "degraded";
  database: boolean;
  redis: boolean;
}

/** `/health/ready` answers 503 with the same body when a dependency is down. */
export function fetchReadiness(): Promise<ReadinessStatus> {
  return apiRequest<ReadinessStatus>("/health/ready", { acceptStatuses: [503], cache: "no-store" });
}
