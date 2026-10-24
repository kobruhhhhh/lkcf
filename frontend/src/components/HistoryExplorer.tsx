import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../lib/api";
import {
  fmtDate,
  fmtLocalDate,
  fmtLocalTime,
  fmtMw,
  fmtSignedMw,
  fmtSignedPct,
} from "../lib/format";
import type { ForecastHistoryResponse } from "../lib/types";

interface HistoryExplorerProps {
  start: string;
  end: string;
}

const times = Array.from({ length: 48 }, (_, index) => {
  const hour = Math.floor(index / 2);
  const minute = index % 2 === 0 ? "00" : "30";
  return `${String(hour).padStart(2, "0")}:${minute}`;
});

export function HistoryExplorer({ start, end }: HistoryExplorerProps) {
  const [date, setDate] = useState("2026-01-15");
  const [time, setTime] = useState("12:30");
  const [history, setHistory] = useState<ForecastHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const days = useMemo(() => {
    const values: string[] = [];
    const cursor = new Date(`${start}T00:00:00Z`);
    const last = new Date(`${end}T00:00:00Z`);
    while (cursor <= last) {
      values.push(cursor.toISOString().slice(0, 10));
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    return values;
  }, [start, end]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .history(`${date}T${time}:00Z`, controller.signal)
      .then((response) => {
        setHistory(response);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setLoading(false);
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Could not reach the forecast history endpoint.",
        );
      });
    return () => controller.abort();
  }, [date, time, reload]);

  const selected = history?.versions.find((version) => version.selected) ?? null;
  const eligible = history?.versions.filter((version) => version.eligible).length ?? 0;
  const afterCutoff =
    history?.versions.filter((version) => version.after_cutoff).length ?? 0;

  const delta =
    selected && history?.actual_mw !== null && history?.actual_mw !== undefined
      ? selected.forecast_mw - history.actual_mw
      : null;
  const deltaPct =
    delta !== null && history?.actual_mw
      ? (delta / history.actual_mw) * 100
      : null;

  return (
    <section id="history" className="card mt-4" aria-busy={loading}>
      <div className="card-header">
        <div>
          <h2 className="section-title">Forecast history</h2>
          <p className="section-subtitle">
            WINDFOR versions for one delivery period, including versions published after
            the cutoff.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="mb-1 block text-[11px] text-body" htmlFor="history-date">
              Delivery date
            </label>
            <select
              id="history-date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="select"
            >
              {days.map((day) => (
                <option key={day} value={day}>
                  {fmtDate(day)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-body" htmlFor="history-time">
              Time
            </label>
            <select
              id="history-time"
              value={time}
              onChange={(event) => setTime(event.target.value)}
              className="select"
            >
              {times.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-start gap-3 px-4 py-8 sm:px-5">
          <p className="flex items-start gap-2 text-sm text-body">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber" />
            {error}
          </p>
          <button
            type="button"
            onClick={() => setReload((value) => value + 1)}
            className="btn"
          >
            <RefreshCw size={13} />
            Retry
          </button>
        </div>
      ) : loading || !history ? (
        <p className="px-4 py-8 text-sm text-body sm:px-5">Loading forecast versions…</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-4 border-b border-line px-4 py-4 sm:grid-cols-4 sm:px-5">
            <div>
              <dt className="text-[11px] text-body">Selected forecast</dt>
              <dd className="mt-1 text-base font-semibold tabular-nums text-ink">
                {fmtMw(selected?.forecast_mw)} MW
                <span className="mt-0.5 block text-[11px] font-normal text-faint">
                  {selected
                    ? `${fmtLocalDate(selected.publish_time_local)} ${fmtLocalTime(selected.publish_time_local)}`
                    : "No eligible version"}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-body">Actual</dt>
              <dd className="mt-1 text-base font-semibold tabular-nums text-ink">
                {fmtMw(history.actual_mw)} MW
                <span className="mt-0.5 block text-[11px] font-normal text-faint">
                  Elexon outturn
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-body">Error</dt>
              <dd
                className={`mt-1 text-base font-semibold tabular-nums ${
                  delta === null ? "text-ink" : delta > 0 ? "text-amber" : "text-teal"
                }`}
              >
                {fmtSignedMw(delta)} MW
                <span className="mt-0.5 block text-[11px] font-normal text-faint">
                  {fmtSignedPct(deltaPct)}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-body">Decision cutoff</dt>
              <dd className="mt-1 text-base font-semibold tabular-nums text-ink">
                {fmtLocalTime(history.cutoff_local)}
                <span className="mt-0.5 block text-[11px] font-normal text-faint">
                  {fmtLocalDate(history.cutoff_local)} · Europe/London
                </span>
              </dd>
            </div>
          </dl>

          <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3 text-xs text-body sm:px-5">
            <p>
              {history.versions.length} versions · {eligible} eligible · {afterCutoff} after
              cutoff
            </p>
            <p className="text-faint">
              Delivery {fmtLocalDate(history.delivery_start_local)}{" "}
              {fmtLocalTime(history.delivery_start_local)} · SP{" "}
              {history.settlement_period}
            </p>
          </div>

          {!history.has_eligible ? (
            <p className="mx-4 mt-3 rounded-md border border-line bg-amber-soft px-3 py-2 text-xs text-amber sm:mx-5">
              {history.message ??
                "No forecast was published on or before the decision cutoff. This period is excluded from metrics."}
            </p>
          ) : null}

          <div
            className="mx-4 my-3 max-h-[360px] overflow-auto rounded-md border border-line sm:mx-5"
            tabIndex={0}
            role="region"
            aria-label="WINDFOR versions for the selected delivery period"
          >
            <table className="w-full min-w-[520px] border-collapse">
              <caption className="sr-only">
                Forecast versions for the selected delivery period, showing publication
                time, forecast, lead time and cutoff eligibility.
              </caption>
              <thead className="sticky top-0 bg-subtle">
                <tr className="border-b border-line">
                  <th className="th sticky top-0 z-10 bg-subtle">Published (local)</th>
                  <th className="th sticky top-0 z-10 bg-subtle text-right">Forecast MW</th>
                  <th className="th sticky top-0 z-10 bg-subtle text-right">Lead time</th>
                  <th className="th sticky top-0 z-10 bg-subtle">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.versions.map((version) => (
                  <tr
                    key={version.publish_time_utc}
                    aria-current={version.selected ? "true" : undefined}
                    className={`border-b border-line last:border-0 ${
                      version.selected
                        ? "bg-accent-soft"
                        : version.after_cutoff
                          ? "text-faint"
                          : ""
                    }`}
                  >
                    <td className="td text-[11px]">
                      {fmtLocalDate(version.publish_time_local)}{" "}
                      {fmtLocalTime(version.publish_time_local)}
                    </td>
                    <td className="td text-right tabular-nums">
                      {fmtMw(version.forecast_mw)}
                    </td>
                    <td className="td text-right tabular-nums">
                      {version.lead_hours.toFixed(1)} h
                    </td>
                    <td
                      className={`td ${
                        version.selected
                          ? "font-medium text-accent-text"
                          : version.after_cutoff
                            ? "text-amber"
                            : "text-body"
                      }`}
                    >
                      {version.selected
                        ? "Selected"
                        : version.after_cutoff
                          ? "After cutoff"
                          : "Eligible"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="border-t border-line px-4 py-2.5 text-[11px] text-faint sm:px-5">
            Only versions published on or before the cutoff are eligible. Post-cutoff
            versions are shown for context and are never selected. Scroll the table to view post-cutoff versions.
          </p>
        </>
      )}
    </section>
  );
}
