const number = new Intl.NumberFormat("en-GB", {
  maximumFractionDigits: 0,
});

const oneDecimal = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const twoDecimals = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function fmtMw(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (digits === 1) return oneDecimal.format(value);
  if (digits === 2) return twoDecimals.format(value);
  return number.format(Math.round(value));
}

export function fmtSignedMw(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const formatted = fmtMw(Math.abs(value), digits);
  if (Math.abs(value) < 0.05) return formatted;
  return `${value > 0 ? "+" : "−"}${formatted}`;
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function fmtSignedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Math.abs(value) < 0.05) return `${value.toFixed(digits)}%`;
  return `${value > 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}%`;
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace("T", " ").replace(/(\.\d+)?Z$/, " UTC").replace("+00:00", " UTC");
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(date);
}

export function fmtDateLong(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function fmtLocalTime(value: string | null | undefined): string {
  if (!value) return "—";
  const match = value.match(/T(\d{2}:\d{2})/);
  return match?.[1] ?? value;
}

export function fmtLocalDate(value: string | null | undefined): string {
  if (!value) return "—";
  return fmtDate(value.slice(0, 10));
}

export const STATUS_LABELS: Record<string, string> = {
  matched: "Matched",
  missing_actual: "Missing actual",
  no_eligible_forecast: "No eligible forecast",
  missing_forecast: "Missing forecast",
};
