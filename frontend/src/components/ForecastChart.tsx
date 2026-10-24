import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import {
  fmtLocalDate,
  fmtLocalTime,
  fmtMw,
  fmtSignedMw,
  STATUS_LABELS,
} from "../lib/format";
import type { AnalysisMeta, TimeseriesPoint } from "../lib/types";

interface ForecastChartProps {
  data: TimeseriesPoint[];
  meta: AnalysisMeta;
}

interface ChartPoint {
  ts: number;
  local: string;
  forecast: number | null;
  actual: number | null;
  error: number | null;
  status: string;
}

function toChartPoint(point: TimeseriesPoint): ChartPoint {
  return {
    ts: new Date(point.delivery_start_utc).getTime(),
    local: point.delivery_start_local,
    forecast: point.forecast_mw,
    actual: point.actual_mw,
    error: point.error_mw,
    status: point.status,
  };
}

function ForecastTooltip({ active, payload }: TooltipProps<ValueType, NameType>) {
  const point = payload?.[0]?.payload as ChartPoint | undefined;
  if (!active || !point) return null;
  return (
    <div className="tooltip min-w-[210px]">
      <p className="text-[11px] text-body">
        {fmtLocalDate(point.local)} · {fmtLocalTime(point.local)}
      </p>
      <dl className="mt-2 space-y-1">
        <div className="flex items-center justify-between gap-6">
          <dt className="text-body">Actual</dt>
          <dd className="tabular-nums">{fmtMw(point.actual)} MW</dd>
        </div>
        <div className="flex items-center justify-between gap-6">
          <dt className="text-body">Forecast</dt>
          <dd className="tabular-nums">{fmtMw(point.forecast)} MW</dd>
        </div>
        <div className="flex items-center justify-between gap-6 border-t border-line pt-1">
          <dt className="text-body">Error</dt>
          <dd
            className={`tabular-nums ${
              point.error === null ? "" : point.error > 0 ? "text-amber" : "text-teal"
            }`}
          >
            {fmtSignedMw(point.error)} MW
          </dd>
        </div>
      </dl>
      {point.status !== "matched" ? (
        <p className="mt-1.5 text-[11px] text-amber">
          {STATUS_LABELS[point.status] ?? point.status}
        </p>
      ) : null}
    </div>
  );
}

export function ForecastChart({ data, meta }: ForecastChartProps) {
  const chartData = useMemo(() => data.map(toChartPoint), [data]);

  const tickFormatter = (value: number) =>
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      timeZone: "Europe/London",
    }).format(new Date(value));

  return (
    <section id="forecast" className="card">
      <div className="card-header">
        <div>
          <h2 className="section-title">Actual vs forecast</h2>
          <p className="section-subtitle">
            Selected WINDFOR publication against Elexon wind outturn, MW
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-body">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-[var(--chart-forecast)]" />
            Forecast
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-[var(--chart-actual)]" />
            Actual
          </span>
        </div>
      </div>

      <div className="h-[320px] px-1 py-3 sm:px-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 24, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="ts"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={tickFormatter}
              minTickGap={48}
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              axisLine={{ stroke: "var(--line)" }}
              tickLine={false}
              dy={6}
            />
            <YAxis
              tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={40}
              domain={[0, (dataMax: number) => Math.ceil((dataMax * 1.08) / 1000) * 1000]}
            />
            <Tooltip
              content={<ForecastTooltip />}
              cursor={{ stroke: "var(--line-strong)", strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="var(--chart-actual)"
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
              connectNulls={false}
              name="Actual"
            />
            <Line
              type="monotone"
              dataKey="forecast"
              stroke="var(--chart-forecast)"
              strokeWidth={1.75}
              dot={false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
              connectNulls={false}
              name="Forecast"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="border-t border-line px-4 py-2.5 text-[11px] text-faint sm:px-5">
        Hourly WINDFOR values are applied to both half-hours in each delivery hour.
        Missing values are shown as gaps, not zero.
        <span className="ml-2 font-mono">
          {meta.forecast_mapping} · {meta.timezone}
        </span>
      </p>
    </section>
  );
}
