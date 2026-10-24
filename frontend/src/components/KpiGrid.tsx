import { fmtMw, fmtPct, fmtSignedMw, fmtSignedPct } from "../lib/format";
import type { DataQuality, Kpis } from "../lib/types";

interface KpiGridProps {
  kpis: Kpis;
  quality: DataQuality;
  expectedPeriods: number;
}

export function KpiGrid({ kpis, quality, expectedPeriods }: KpiGridProps) {
  const biasTone =
    kpis.bias_mw === null
      ? "text-ink"
      : kpis.bias_mw > 0
        ? "text-amber"
        : "text-teal";

  return (
    <section aria-label="Headline metrics">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <article className="card p-4">
          <p className="text-xs font-medium text-body">MAE</p>
          <p className="mt-2 text-xl font-semibold tabular-nums tracking-tight text-ink sm:text-2xl">
            {fmtMw(kpis.mae_mw)} <span className="text-sm font-normal text-body">MW</span>
          </p>
          <p className="mt-1 text-xs text-faint">Mean absolute error</p>
        </article>

        <article className="card p-4">
          <p className="text-xs font-medium text-body">RMSE</p>
          <p className="mt-2 text-xl font-semibold tabular-nums tracking-tight text-ink sm:text-2xl">
            {fmtMw(kpis.rmse_mw)} <span className="text-sm font-normal text-body">MW</span>
          </p>
          <p className="mt-1 text-xs text-faint">Root mean squared error</p>
        </article>

        <article className="card p-4">
          <p className="text-xs font-medium text-body">Forecast bias</p>
          <p
            className={`mt-2 text-xl font-semibold tabular-nums tracking-tight sm:text-2xl ${biasTone}`}
          >
            {fmtSignedMw(kpis.bias_mw)}{" "}
            <span className="text-sm font-normal text-body">MW</span>
          </p>
          <p className="mt-1 text-xs text-faint">
            {fmtSignedPct(kpis.bias_pct_of_mean_actual)} of mean actual
          </p>
        </article>

        <article className="card p-4">
          <p className="text-xs font-medium text-body">MAPE</p>
          <p className="mt-2 text-xl font-semibold tabular-nums tracking-tight text-ink sm:text-2xl">
            {fmtPct(kpis.mape_pct, 2)}
          </p>
          <p className="mt-1 text-xs text-faint">
            {kpis.mape_excluded_zero_actual.toLocaleString("en-GB")} zero-actual periods
            excluded
          </p>
        </article>

        <article className="card col-span-2 p-4 lg:col-span-1">
          <p className="text-xs font-medium text-body">Matched coverage</p>
          <p className="mt-2 text-xl font-semibold tabular-nums tracking-tight text-ink sm:text-2xl">
            {fmtPct(quality.matched_coverage_pct, 1)}
          </p>
          <p className="mt-1 text-xs text-faint">
            {quality.matched_periods.toLocaleString("en-GB")} of{" "}
            {expectedPeriods.toLocaleString("en-GB")} periods
          </p>
        </article>
      </div>
    </section>
  );
}
