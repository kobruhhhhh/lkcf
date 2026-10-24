import { useCallback, useEffect, useState } from "react";

import { AccuracyPanel } from "./components/AccuracyPanel";
import { DataStatus } from "./components/DataStatus";
import { ErrorDistribution } from "./components/ErrorDistribution";
import { ForecastChart } from "./components/ForecastChart";
import { Header } from "./components/Header";
import { HistoryExplorer } from "./components/HistoryExplorer";
import { KpiGrid } from "./components/KpiGrid";
import { Methodology } from "./components/Methodology";
import { SettlementTable } from "./components/SettlementTable";
import { ErrorScreen, LoadingScreen } from "./components/States";
import { api, ApiError } from "./lib/api";
import { fmtDateLong } from "./lib/format";
import type {
  AccuracyResponse,
  DataStatusResponse,
  SummaryResponse,
  TimeseriesResponse,
} from "./lib/types";

interface DashboardData {
  summary: SummaryResponse;
  timeseries: TimeseriesResponse;
  accuracy: AccuracyResponse;
}

type Theme = "light" | "dark";
const THEME_KEY = "windtrace-theme";

function initialTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function describeError(caught: unknown, fallback: string): string {
  if (caught instanceof ApiError) {
    return `${caught.message} (HTTP ${caught.status})`;
  }
  return fallback;
}

async function fetchDashboard(signal?: AbortSignal): Promise<DashboardData> {
  const [summary, timeseries, accuracy] = await Promise.all([
    api.summary(signal),
    api.timeseries(signal),
    api.accuracy(signal),
  ]);
  return { summary, timeseries, accuracy };
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<DataStatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  const toggleTheme = useCallback(
    () => setTheme((value) => (value === "dark" ? "light" : "dark")),
    [],
  );

  const refreshData = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    setStatusError(null);
    try {
      const nextStatus = await api.refresh();
      setStatus(nextStatus);
      const nextData = await fetchDashboard();
      setData(nextData);
    } catch (caught: unknown) {
      const message = describeError(
        caught,
        "Could not refresh the live Elexon data. Check the backend connection.",
      );
      setStatusError(message);
      if (!data) setError(message);
      try {
        setStatus(await api.dataStatus());
      } catch {
        // The status error above already explains the failed refresh.
      }
    } finally {
      setRefreshing(false);
    }
  }, [data]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Storage can be unavailable in private or restricted contexts.
    }
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#171a18" : "#ffffff");
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();
    fetchDashboard(controller.signal)
      .then(setData)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(
          describeError(
            caught,
            "Could not reach the WindTrace API. Check that the backend is running and CORS allows this origin.",
          ),
        );
      });

    api
      .dataStatus(controller.signal)
      .then((nextStatus) => {
        setStatus(nextStatus);
        setStatusError(null);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setStatusError(
          describeError(caught, "Could not read the live data status."),
        );
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="min-h-screen">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:text-ink focus:ring-1 focus:ring-line"
      >
        Skip to content
      </a>
      <Header theme={theme} onToggleTheme={toggleTheme} />

      {error ? (
        <ErrorScreen
          message={error}
          apiBase={api.baseUrl}
          busy={refreshing}
          onRetry={() => void refreshData()}
        />
      ) : !data ? (
        <LoadingScreen />
      ) : (
        <main id="content" className="mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-6 lg:px-8">
          <section id="overview" className="mb-5">
            <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-ink">
                  Wind forecast accuracy
                </h1>
                <p className="mt-1 text-sm text-body">
                  January 2026 · GB wind outturn vs day-ahead forecast
                </p>
              </div>
              <p className="text-xs text-faint">
                {fmtDateLong(data.summary.meta.analysis_start)} to{" "}
                {fmtDateLong(data.summary.meta.analysis_end)} ·{" "}
                {data.summary.meta.expected_periods.toLocaleString("en-GB")} settlement
                periods
              </p>
            </div>
            <DataStatus
              status={status}
              error={statusError}
              refreshing={refreshing}
              onRefresh={() => void refreshData()}
            />
          </section>

          <KpiGrid
            kpis={data.summary.kpis}
            quality={data.summary.data_quality}
            expectedPeriods={data.summary.meta.expected_periods}
          />

          <div className="mt-4">
            <ForecastChart data={data.timeseries.data} meta={data.summary.meta} />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr]">
            <AccuracyPanel accuracy={data.accuracy} />
            <ErrorDistribution distribution={data.accuracy.error_distribution} />
          </div>

          <SettlementTable data={data.timeseries.data} />

          <HistoryExplorer
            start={data.summary.meta.analysis_start}
            end={data.summary.meta.analysis_end}
          />

          <Methodology summary={data.summary} definitions={data.accuracy.definitions} />
        </main>
      )}

      <footer className="mt-8 border-t border-line bg-subtle">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-2 px-4 py-4 text-xs text-body sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p>
            WindTrace · Elexon FUELHH and WINDFOR
            {data
              ? ` · ${fmtDateLong(data.summary.meta.analysis_start)} to ${fmtDateLong(
                  data.summary.meta.analysis_end,
                )}`
              : ""}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <a
              className="hover:text-ink"
              href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream"
              target="_blank"
              rel="noreferrer"
            >
              FUELHH source
            </a>
            <a
              className="hover:text-ink"
              href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream"
              target="_blank"
              rel="noreferrer"
            >
              WINDFOR source
            </a>
            {status ? (
              <span className="text-faint">
                {status.mode === "live" ? "Live API" : "Offline snapshot"}
              </span>
            ) : null}
          </div>
        </div>
      </footer>
    </div>
  );
}
