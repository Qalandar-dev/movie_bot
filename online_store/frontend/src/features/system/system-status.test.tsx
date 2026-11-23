import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderWithQuery } from "@/test/utils";

import { SystemStatus } from "./system-status";

describe("SystemStatus", () => {
  it("shows each dependency's state from the readiness endpoint", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ status: "degraded", database: true, redis: false }, 503),
    );
    renderWithQuery(<SystemStatus />);
    expect(screen.getByRole("status")).toHaveTextContent("Tekshirilmoqda");
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("PostgreSQL");
    expect(rows[1]).toHaveTextContent("Ishlayapti");
    expect(rows[2]).toHaveTextContent("Ulanmagan");
  });

  it("shows an error with a retry button when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderWithQuery(<SystemStatus />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server bilan bog‘lanib bo‘lmadi");
    expect(screen.getByRole("button", { name: /Qayta urinish/ })).toBeEnabled();
  });
});
