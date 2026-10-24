import { useMemo, useState } from "react";

import {
  fmtLocalDate,
  fmtLocalTime,
  fmtMw,
  fmtSignedMw,
  STATUS_LABELS,
} from "../lib/format";
import type { PeriodStatus, TimeseriesPoint } from "../lib/types";

interface SettlementTableProps {
  data: TimeseriesPoint[];
}

const PAGE_SIZE = 25;

function statusClass(status: PeriodStatus): string {
  if (status === "matched") return "text-accent-text";
  if (status === "no_eligible_forecast") return "text-amber";
  return "text-danger";
}

export function SettlementTable({ data }: SettlementTableProps) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(data.length / PAGE_SIZE));
  const current = Math.min(page, pageCount - 1);

  const rows = useMemo(
    () => data.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE),
    [data, current],
  );

  const first = data.length ? current * PAGE_SIZE + 1 : 0;
  const last = Math.min((current + 1) * PAGE_SIZE, data.length);

  return (
    <section id="settlements" className="card mt-4">
      <div className="card-header">
        <div>
          <h2 className="section-title">Settlement periods</h2>
          <p className="section-subtitle">
            Actual generation, selected forecast and error for each half-hour. Times are
            local.
          </p>
        </div>
        <p className="text-xs text-body" aria-live="polite">
          {first.toLocaleString("en-GB")}–{last.toLocaleString("en-GB")} of{" "}
          {data.length.toLocaleString("en-GB")}
        </p>
      </div>

        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label="Settlement periods table"
        >
        <table className="w-full min-w-[760px] border-collapse">
          <caption className="sr-only">
            January 2026 settlement periods with actual wind generation, selected
            day-ahead forecast, error, publication time and status.
          </caption>
          <thead className="bg-subtle">
            <tr className="border-b border-line">
              <th className="th">Delivery</th>
              <th className="th text-right">SP</th>
              <th className="th text-right">Actual MW</th>
              <th className="th text-right">Selected forecast MW</th>
              <th className="th text-right">Error MW</th>
              <th className="th">Published (local)</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.delivery_start_utc}
                className="border-b border-line last:border-0 hover:bg-subtle"
              >
                <td className="td">
                  {fmtLocalDate(row.delivery_start_local)}{" "}
                  <span className="text-body">{fmtLocalTime(row.delivery_start_local)}</span>
                </td>
                <td className="td text-right tabular-nums">{row.settlement_period}</td>
                <td className="td text-right tabular-nums">{fmtMw(row.actual_mw)}</td>
                <td className="td text-right tabular-nums">{fmtMw(row.forecast_mw)}</td>
                <td
                  className={`td text-right tabular-nums ${
                    row.error_mw === null
                      ? "text-faint"
                      : row.error_mw > 0
                        ? "text-amber"
                        : "text-teal"
                  }`}
                >
                  {fmtSignedMw(row.error_mw)}
                </td>
                <td className="td text-[11px] text-body">
                  {row.forecast_publish_time_local ? (
                    <>
                      {fmtLocalDate(row.forecast_publish_time_local)}{" "}
                      {fmtLocalTime(row.forecast_publish_time_local)}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={`td ${statusClass(row.status)}`}>
                  {STATUS_LABELS[row.status] ?? row.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5">
        <p className="text-[11px] text-faint" aria-live="polite">
          Page {current + 1} of {pageCount}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn"
            onClick={() => setPage((value) => Math.max(0, value - 1))}
            disabled={current === 0}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}
            disabled={current >= pageCount - 1}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
