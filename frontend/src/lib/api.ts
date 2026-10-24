import type {
  AccuracyResponse,
  DataStatusResponse,
  ForecastHistoryResponse,
  SummaryResponse,
  TimeseriesResponse,
} from "./types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!configuredBaseUrl || !configuredBaseUrl.trim()) {
  throw new Error(
    "VITE_API_BASE_URL is not configured. Copy frontend/.env.example to frontend/.env " +
      "and set it to the backend API origin, then restart or rebuild the frontend.",
  );
}

const API_BASE = configuredBaseUrl.trim().replace(/\/+$/, "");

if (!/^(https?:\/\/|\/)/i.test(API_BASE)) {
  throw new Error(
    `VITE_API_BASE_URL must be an absolute http(s) URL or a root-relative path; received "${API_BASE}".`,
  );
}

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function extractMessage(payload: unknown): string {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const candidate = detail as { message?: unknown; code?: unknown };
      if (typeof candidate.message === "string") return candidate.message;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
  }
  return "The analytics API returned an unexpected response.";
}

function extractCode(payload: unknown): string | null {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (detail && typeof detail === "object") {
      const code = (detail as { code?: unknown }).code;
      if (typeof code === "string") return code;
    }
  }
  return null;
}

async function fetchJson<T>(
  path: string,
  signal?: AbortSignal,
  method: "GET" | "POST" = "GET",
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    method,
    headers: { Accept: "application/json" },
  });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    throw new ApiError(extractMessage(payload), response.status, extractCode(payload));
  }
  return payload as T;
}

export const api = {
  baseUrl: API_BASE,
  dataStatus: (signal?: AbortSignal) =>
    fetchJson<DataStatusResponse>("/api/data-status", signal),
  refresh: (signal?: AbortSignal) =>
    fetchJson<DataStatusResponse>("/api/refresh", signal, "POST"),
  summary: (signal?: AbortSignal) => fetchJson<SummaryResponse>("/api/summary", signal),
  timeseries: (signal?: AbortSignal) =>
    fetchJson<TimeseriesResponse>("/api/timeseries", signal),
  accuracy: (signal?: AbortSignal) => fetchJson<AccuracyResponse>("/api/accuracy", signal),
  history: (deliveryStart: string, signal?: AbortSignal) =>
    fetchJson<ForecastHistoryResponse>(
      `/api/forecast-history?delivery_start=${encodeURIComponent(deliveryStart)}`,
      signal,
    ),
};
