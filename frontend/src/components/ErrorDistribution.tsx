import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fmtSignedMw } from "../lib/format";
import type { ErrorDistribution as Distribution } from "../lib/types";

interface ErrorDistributionProps {
  distribution: Distribution;
}

export function ErrorDistribution({ distribution }: ErrorDistributionProps) {
  const data = distribution.bins.map((bin) => ({
    mid: (bin.from_mw + bin.to_mw) / 2,
    label: `${fmtSignedMw(bin.from_mw)} to ${fmtSignedMw(bin.to_mw)} MW`,
    count: bin.count,
  }));

  const minimum = data.length ? Math.floor(data[0].mid / 2000) * 2000 : -2000;
  const maximum = data.length
    ? Math.ceil(data[data.length - 1].mid / 2000) * 2000
    : 2000;
  const ticks = Array.from(
    { length: Math.floor((maximum - minimum) / 2000) + 1 },
    (_, index) => minimum + index * 2000,
  );

  return (
    <section className="card flex h-full flex-col">
      <div className="card-header">
        <div>
          <h2 className="section-title">Forecast error</h2>
          <p className="section-subtitle">Forecast minus actual, MW</p>
        </div>
        <p className="text-xs text-body">
          Mean <span className="tabular-nums text-ink">{fmtSignedMw(distribution.mean_mw)} MW</span>
        </p>
      </div>

      <div className="h-[230px] px-1 py-3 sm:px-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
            barCategoryGap={0}
          >
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="mid"
              type="number"
              domain={["dataMin", "dataMax"]}
              ticks={ticks}
              tickFormatter={(value: number) => `${value / 1000}k`}
              tick={{ fill: "var(--chart-axis)", fontSize: 10.5 }}
              axisLine={{ stroke: "var(--line)" }}
              tickLine={false}
              dy={6}
            />
            <YAxis
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={34}
            />
            <Tooltip
              content={({ active, payload }) => {
                const bin = payload?.[0]?.payload as
                  | { label: string; count: number }
                  | undefined;
                if (!active || !bin) return null;
                return (
                  <div className="tooltip">
                    <p className="font-medium">{bin.label}</p>
                    <p className="mt-1 tabular-nums text-body">
                      {bin.count.toLocaleString("en-GB")} periods
                    </p>
                  </div>
                );
              }}
              cursor={{ fill: "var(--subtle)" }}
            />
            <ReferenceLine x={0} stroke="var(--line-strong)" strokeDasharray="3 3" />
            <Bar dataKey="count" isAnimationActive={false} barSize={6} radius={[2, 2, 0, 0]}>
              {data.map((bin) => (
                <Cell
                  key={bin.mid}
                  fill={bin.mid >= 0 ? "var(--chart-positive)" : "var(--chart-negative)"}
                  fillOpacity={0.82}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <dl className="mt-auto grid grid-cols-3 gap-2 border-t border-line px-4 py-3 sm:px-5">
        {[
          { label: "P10", value: distribution.percentiles.p10_mw },
          { label: "Median", value: distribution.percentiles.p50_mw },
          { label: "P90", value: distribution.percentiles.p90_mw },
        ].map((item) => (
          <div key={item.label}>
            <dt className="text-[11px] text-faint">{item.label}</dt>
            <dd className="mt-0.5 text-xs tabular-nums text-ink">
              {fmtSignedMw(item.value)} MW
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
