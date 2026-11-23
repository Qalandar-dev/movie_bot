import { describe, expect, it, vi } from "vitest";

import { jsonResponse } from "@/test/utils";

import { ApiError, apiRequest } from "./api-client";

describe("apiRequest", () => {
  it("returns parsed JSON on success and calls the same-origin API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ a: 1 }));
    await expect(apiRequest("/things")).resolves.toEqual({ a: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/things",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("throws ApiError with the backend error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: { code: "conflict", message: "SKU band", request_id: "r1" } }, 409),
    );
    const err = await apiRequest("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 409,
      code: "conflict",
      message: "SKU band",
      requestId: "r1",
    });
  });

  it("maps network failures to a friendly Uzbek message", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("handles non-JSON error bodies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>502</html>", { status: 502 }),
    );
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("resolves accepted non-2xx statuses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ status: "degraded" }, 503));
    await expect(apiRequest("/x", { acceptStatuses: [503] })).resolves.toEqual({
      status: "degraded",
    });
  });
});
