import { AlertTriangle, RefreshCw } from "lucide-react";

import { fmtDateTime, fmtPct } from "../lib/format";
import type { DataStatusResponse } from "../lib/types";

interface DataStatusProps {
  status: DataStatusResponse | null;
  error: string | null;
  refreshing: boolean;
  onRefresh: () => void;
}

const stateLabels = {
  live: "Live data",
  refreshing: "Refreshing",
  error: "Data error",
  snapshot: "Offline snapshot",
} as const;

const dotClasses = {
  live: "bg-accent",
  refreshing: "bg-amber",
  error: "bg-danger",
  snapshot: "bg-faint",
} as const;

export function DataStatus({
  status,
  error,
  refreshing,
  onRefresh,
}: DataStatusProps) {
  const state = refreshing ? "refreshing" : error ? "error" : (status?.status ?? "refreshing");
  const source = status?.source ?? "Elexon BMRS";
  const updated = status?.last_successful_fetch_at;
  const coverage = status?.matched_coverage_pct;

  return (
    <section
      className="mt-3 rounded-md border border-line bg-subtle px-3 py-2"
      aria-label="Data source status"
      aria-busy={refreshing}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div
          className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-body"
          role="status"
          aria-live="polite"
        >
          <span className="inline-flex items-center gap-1.5 font-medium text-ink">
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClasses[state]}`}
              aria-hidden="true"
            />
            {stateLabels[state]}
          </span>
          <span aria-hidden="true" className="text-faint">
            ·
          </span>
          <span>{source}</span>
          {updated ? (
            <>
              <span aria-hidden="true" className="text-faint">
                ·
              </span>
              <span>Updated {fmtDateTime(updated)}</span>
            </>
          ) : null}
          {coverage !== null && coverage !== undefined ? (
            <>
              <span aria-hidden="true" className="text-faint">
                ·
              </span>
              <span>{fmtPct(coverage, 1)} matched</span>
            </>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="btn bg-surface"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : undefined} />
          {refreshing ? "Refreshing…" : "Refresh data"}
        </button>
      </div>

      {error ? (
        <p className="mt-1.5 flex items-start gap-1.5 text-[11px] leading-relaxed text-danger">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>{error} Showing the last successfully loaded data.</span>
        </p>
      ) : null}
    </section>
  );
}
