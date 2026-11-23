import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const uzsFormatter = new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 });

/**
 * Format an amount in Uzbek so'm, e.g. `1 250 000 so‘m`.
 * Amounts arrive from the API as decimal strings to avoid float rounding.
 */
export function formatUZS(amount: string | number): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) return "—";
  // Normalise any locale-specific space characters to a regular non-breaking space.
  const digits = uzsFormatter.format(Math.round(value)).replace(/[\s  ]/g, " ");
  return `${digits} so‘m`;
}
