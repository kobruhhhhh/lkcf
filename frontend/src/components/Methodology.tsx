import { fmtDateTime, fmtPct } from "../lib/format";
import type { SummaryResponse } from "../lib/types";

interface MethodologyProps {
  summary: SummaryResponse;
  definitions: Record<string, string>;
}

const labels: Record<string, string> = {
  mae: "MAE",
  rmse: "RMSE",
  bias: "Bias",
  bias_pct: "Bias %",
  mape: "MAPE",
  smape: "sMAPE",
  wape: "WAPE",
  coverage: "Coverage",
  lead_time: "Lead time",
};

export function Methodology({ summary, definitions }: MethodologyProps) {
  const { meta, data_quality: quality } = summary;
  const sources = meta.source_urls;
  const sourceLabel =
    meta.data_source === "live"
      ? "Live Elexon FUELHH and WINDFOR data"
      : "Offline Elexon FUELHH and WINDFOR snapshot";
  const notableWarnings = quality.warnings.filter(
    (warning) => !warning.startsWith("Hourly WINDFOR"),
  );

  return (
    <section id="methodology" className="card mt-4">
      <div className="card-header">
        <div>
          <h2 className="section-title">Methodology</h2>
          <p className="section-subtitle">
            Vintage control, hourly mapping and metric definitions.
          </p>
        </div>
      </div>

      <div className="grid gap-5 px-4 py-4 sm:px-5 lg:grid-cols-3">
        <div>
          <h3 className="text-xs font-semibold text-ink">Decision cutoff</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-body">
            {meta.cutoff.local_time} {meta.cutoff.timezone} on the day before delivery,
            inclusive. The selected forecast is the latest WINDFOR publication at or
            before that cutoff. This is a pilot assumption based on EPEX GB day-ahead
            gate-closure context, not an official Elexon rule.
          </p>
        </div>
        <div>
          <h3 className="text-xs font-semibold text-ink">Hourly to half-hourly</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-body">
            {meta.forecast_mapping_note} The mapping is flagged as{" "}
            <span className="font-mono text-[11px]">{meta.forecast_mapping}</span>.
          </p>
        </div>
        <div>
          <h3 className="text-xs font-semibold text-ink">Scoring and missing data</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-body">
            Metrics use matched actual and forecast pairs only. Missing generation is
            never zero-filled, and a post-cutoff forecast is never substituted. MAPE
            excludes zero-actual periods and reports the excluded count; coverage shows
            matched periods over expected periods.
          </p>
        </div>
      </div>

      <div className="border-t border-line px-4 py-4 sm:px-5">
        <h3 className="text-xs font-semibold text-ink">Metric definitions</h3>
        <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(definitions).map(([key, text]) => (
            <div key={key}>
              <dt className="text-xs font-medium text-ink">{labels[key] ?? key}</dt>
              <dd className="mt-0.5 text-[11px] leading-relaxed text-body">{text}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="border-t border-line bg-subtle px-4 py-4 text-[11px] leading-relaxed text-body sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-ink">Data and coverage</h3>
          <p className="text-[10px] text-faint">{sourceLabel}</p>
        </div>
        <p className="mt-1.5">
          Matched {quality.matched_periods.toLocaleString("en-GB")} of{" "}
          {meta.expected_periods.toLocaleString("en-GB")} periods matched (
          {fmtPct(quality.matched_coverage_pct, 1)}) ·{" "}
          {quality.actual_records.toLocaleString("en-GB")} FUELHH rows ·{" "}
          {quality.forecast_records.toLocaleString("en-GB")} WINDFOR rows ·{" "}
          {quality.missing_actual_periods} missing actual ·{" "}
          {quality.missing_forecast_periods} missing forecast ·{" "}
          {quality.no_eligible_forecast_periods} with no eligible forecast.
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          <a className="hover:text-ink" href={sources.fuelhh} target="_blank" rel="noreferrer">
            FUELHH
          </a>
          <a className="hover:text-ink" href={sources.windfor} target="_blank" rel="noreferrer">
            WINDFOR
          </a>
          <a
            className="hover:text-ink"
            href={sources.windfor_evolution}
            target="_blank"
            rel="noreferrer"
          >
            WINDFOR evolution
          </a>
          <span>Fetched {fmtDateTime(meta.data_fetched_at)}</span>
        </div>
        {notableWarnings.length ? (
          <ul className="mt-2 space-y-1 text-amber">
            {notableWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
