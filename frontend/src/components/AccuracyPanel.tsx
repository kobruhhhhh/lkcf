import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fmtMw, fmtPct, fmtSignedMw } from "../lib/format";
import type { AccuracyGroup, AccuracyResponse } from "../lib/types";

interface AccuracyPanelProps {
  accuracy: AccuracyResponse;
}

type TabId = "day" | "hour";

const tabs: Array<{ id: TabId; label: string; caption: string }> = [
  { id: "day", label: "By day", caption: "Mean absolute error by delivery day" },
  { id: "hour", label: "By hour", caption: "Mean absolute error by local delivery hour" },
];

function GroupTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: AccuracyGroup }>;
}) {
  const group = payload?.[0]?.payload;
  if (!active || !group) return null;
  return (
    <div className="tooltip min-w-[190px]">
      <p className="font-medium">{group.label}</p>
      <dl className="mt-2 space-y-1">
        <div className="flex items-center justify-between gap-6">
          <dt className="text-body">MAE</dt>
          <dd className="tabular-nums">{fmtMw(group.mae_mw)} MW</dd>
        </div>
        <div className="flex items-center justify-between gap-6">
          <dt className="text-body">Bias</dt>
          <dd className="tabular-nums">{fmtSignedMw(group.bias_mw)} MW</dd>
        </div>
        <div className="flex items-center justify-between gap-6">
          <dt className="text-body">MAPE</dt>
          <dd className="tabular-nums">{fmtPct(group.mape_pct)}</dd>
        </div>
        <div className="flex items-center justify-between gap-6 border-t border-line pt-1">
          <dt className="text-body">Coverage</dt>
          <dd className="tabular-nums">
            {group.matched}/{group.expected}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function AccuracyPanel({ accuracy }: AccuracyPanelProps) {
  const [tab, setTab] = useState<TabId>("day");

  const groups = useMemo(
    () => (tab === "day" ? accuracy.by_date : accuracy.by_hour_local),
    [accuracy, tab],
  );
  const caption = tabs.find((item) => item.id === tab)?.caption ?? "";
  const interval = groups.length > 20 ? 2 : 1;

  return (
    <section id="accuracy" className="card flex h-full flex-col">
      <div className="card-header">
        <div>
          <h2 className="section-title">Accuracy breakdown</h2>
          <p className="section-subtitle">{caption}</p>
        </div>
        <div className="flex border-b border-line" role="tablist" aria-label="Accuracy grouping">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              aria-controls="accuracy-chart"
              onClick={() => setTab(item.id)}
              className={`tab ${tab === item.id ? "tab-active" : ""}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div
        id="accuracy-chart"
        role="tabpanel"
        className="h-[290px] flex-1 px-1 py-3 sm:px-3"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={groups}
            margin={{ top: 12, right: 16, bottom: 4, left: 0 }}
            barCategoryGap="22%"
          >
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "var(--chart-axis)", fontSize: 10.5 }}
              axisLine={{ stroke: "var(--line)" }}
              tickLine={false}
              interval={interval}
              dy={6}
            />
            <YAxis
              tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={38}
            />
            <Tooltip
              content={<GroupTooltip />}
              cursor={{ fill: "var(--subtle)" }}
            />
            <ReferenceLine
              y={accuracy.overall.mae_mw ?? 0}
              stroke="var(--line-strong)"
              strokeDasharray="4 4"
              label={{
                value: "Month MAE",
                position: "insideTopRight",
                fill: "var(--chart-axis)",
                fontSize: 10,
              }}
            />
            <Bar
              dataKey="mae_mw"
              fill="var(--chart-forecast)"
              fillOpacity={0.78}
              isAnimationActive={false}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="border-t border-line px-4 py-2.5 text-[11px] text-faint sm:px-5">
        Bars show MAE. The dashed line is the January MAE of{" "}
        {fmtMw(accuracy.overall.mae_mw)} MW.
      </p>
    </section>
  );
}
