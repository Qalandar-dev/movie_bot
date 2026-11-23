/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * The browser always calls the same origin (`/api/v1/...`): Nginx (Docker) or the
 * Next.js dev rewrite forwards it to FastAPI. Same-origin keeps the refresh-token
 * cookie (Phase 5) first-party and avoids CORS in production.
 */

export const API_BASE = "/api/v1";

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | undefined;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

const NETWORK_ERROR: ApiErrorBody = {
  code: "network_error",
  message: "Server bilan bog‘lanib bo‘lmadi. Internet aloqasini tekshiring.",
};

function isErrorEnvelope(value: unknown): value is { error: ApiErrorBody } {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const err = (value as { error: unknown }).error;
  return (
    typeof err === "object" &&
    err !== null &&
    typeof (err as ApiErrorBody).code === "string" &&
    typeof (err as ApiErrorBody).message === "string"
  );
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Resolve these HTTP statuses with their JSON body instead of throwing. */
  acceptStatuses?: number[];
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, acceptStatuses = [], headers, ...init } = options;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, NETWORK_ERROR);
  }

  const text = await response.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = undefined;
    }
  }

  if (response.ok || acceptStatuses.includes(response.status)) {
    return data as T;
  }
  if (isErrorEnvelope(data)) {
    throw new ApiError(response.status, data.error);
  }
  throw new ApiError(response.status, {
    code: "http_error",
    message: `Kutilmagan javob (HTTP ${response.status}).`,
  });
}
