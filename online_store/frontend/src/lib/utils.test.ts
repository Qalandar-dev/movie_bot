import { describe, expect, it } from "vitest";

import { formatUZS } from "./utils";

describe("formatUZS", () => {
  it("formats decimal strings from the API", () => {
    expect(formatUZS("1250000.00")).toBe("1 250 000 so‘m");
  });
  it("rounds to whole so'm", () => {
    expect(formatUZS(999.6)).toBe("1 000 so‘m");
  });
  it("handles invalid input", () => {
    expect(formatUZS("abc")).toBe("—");
  });
});
