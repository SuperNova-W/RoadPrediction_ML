"use client";

import { useReducedMotion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DAMAGE_CLASSES, type DamageClassCode, type MonthlyTrendPoint } from "@/lib/types";
import type { DistrictReportRow } from "@/lib/mock/trends";
import { DAMAGE_COLORS, ORDINAL_BLUE, SERIES, CHART_INK } from "@/lib/tokens";
import { formatCurrencyCompact, formatPercent } from "@/lib/format";
import { districtById } from "@/lib/mock/districts";
import { axisProps, gridProps, ChartLegend, DefaultTooltip } from "./chart-kit";

const CLASS_CODES: DamageClassCode[] = ["D00", "D10", "D20", "D40"];

const classLegend = CLASS_CODES.map((c) => ({
  label: DAMAGE_CLASSES[c].label,
  color: DAMAGE_COLORS[c],
}));

/** Open issues per damage class (identity colors match the map legend). */
export function DamageDistributionChart({
  data,
}: {
  data: { code: DamageClassCode; count: number }[];
}) {
  const animate = !useReducedMotion();
  const rows = data.map((d) => ({
    ...d,
    label: DAMAGE_CLASSES[d.code].short,
  }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 0 }}>
          <XAxis type="number" {...axisProps} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={130}
            {...axisProps}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: CHART_INK.grid, opacity: 0.4 }}
            content={<DefaultTooltip formatter={(v) => `${v} issues`} />}
          />
          <Bar
            dataKey="count"
            name="Open issues"
            barSize={14}
            radius={[0, 4, 4, 0]}
            isAnimationActive={animate}
          >
            {rows.map((r) => (
              <Cell key={r.code} fill={DAMAGE_COLORS[r.code]} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              style={{ fill: CHART_INK.label, fontSize: 11, fontVariantNumeric: "tabular-nums" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** New detections vs resolved per month — two series, one shared axis. */
export function DetectionTrendChart({ data }: { data: MonthlyTrendPoint[] }) {
  const animate = !useReducedMotion();
  return (
    <div className="space-y-2">
      <ChartLegend
        items={[
          { label: "New detections", color: SERIES.blue },
          { label: "Resolved", color: SERIES.teal },
        ]}
      />
      <div className="h-56 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ left: -16, right: 8, top: 6, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="label" {...axisProps} />
            <YAxis {...axisProps} axisLine={false} />
            <Tooltip content={<DefaultTooltip />} />
            <Line
              type="monotone"
              dataKey="detections"
              name="New detections"
              stroke={SERIES.blue}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
              isAnimationActive={animate}
            />
            <Line
              type="monotone"
              dataKey="resolved"
              name="Resolved"
              stroke={SERIES.teal}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
              isAnimationActive={animate}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Open issues by class per district — stacked with surface gaps. */
export function DistrictComparisonChart({
  data,
}: {
  data: DistrictReportRow[];
}) {
  const animate = !useReducedMotion();
  const rows = data.map((d) => {
    const total = d.open;
    // Split totals proportionally for the demo dataset.
    return {
      name: districtById(d.district).name,
      D00: Math.round(total * 0.33),
      D10: Math.round(total * 0.17),
      D20: Math.round(total * 0.28),
      D40: total - Math.round(total * 0.33) - Math.round(total * 0.17) - Math.round(total * 0.28),
    };
  });
  return (
    <div className="space-y-2">
      <ChartLegend items={classLegend} />
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 6, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="name" {...axisProps} interval={0} tick={{ fill: CHART_INK.axis, fontSize: 10 }} />
            <YAxis {...axisProps} axisLine={false} />
            <Tooltip
              cursor={{ fill: CHART_INK.grid, opacity: 0.4 }}
              content={<DefaultTooltip formatter={(v) => `${v} issues`} />}
            />
            {CLASS_CODES.map((code, i) => (
              <Bar
                key={code}
                dataKey={code}
                name={DAMAGE_CLASSES[code].label}
                stackId="a"
                fill={DAMAGE_COLORS[code]}
                stroke="#ffffff"
                strokeWidth={1}
                barSize={26}
                radius={i === CLASS_CODES.length - 1 ? [4, 4, 0, 0] : 0}
                isAnimationActive={animate}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Detections per class over time (stacked area). */
export function ClassTrendsChart({ data }: { data: MonthlyTrendPoint[] }) {
  const animate = !useReducedMotion();
  const rows = data.map((d) => ({ label: d.label, ...d.byClass }));
  return (
    <div className="space-y-2">
      <ChartLegend items={classLegend} />
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <AreaChart data={rows} margin={{ left: -16, right: 8, top: 6, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="label" {...axisProps} />
            <YAxis {...axisProps} axisLine={false} />
            <Tooltip content={<DefaultTooltip formatter={(v) => `${v} detections`} />} />
            {CLASS_CODES.map((code) => (
              <Area
                key={code}
                type="monotone"
                dataKey={code}
                name={DAMAGE_CLASSES[code].label}
                stackId="1"
                stroke={DAMAGE_COLORS[code]}
                strokeWidth={1.5}
                fill={DAMAGE_COLORS[code]}
                fillOpacity={0.22}
                isAnimationActive={animate}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Priority-score distribution — ordered buckets on a one-hue ordinal ramp. */
export function PriorityDistributionChart({
  data,
}: {
  data: { bucket: string; count: number }[];
}) {
  const animate = !useReducedMotion();
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: -16, right: 8, top: 16, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="bucket" {...axisProps} />
          <YAxis {...axisProps} axisLine={false} />
          <Tooltip
            cursor={{ fill: CHART_INK.grid, opacity: 0.4 }}
            content={<DefaultTooltip formatter={(v) => `${v} issues`} />}
          />
          <Bar dataKey="count" name="Issues" barSize={32} radius={[4, 4, 0, 0]} isAnimationActive={animate}>
            {data.map((d, i) => (
              <Cell key={d.bucket} fill={ORDINAL_BLUE[Math.min(i + 1, ORDINAL_BLUE.length - 1)]} />
            ))}
            <LabelList
              dataKey="count"
              position="top"
              style={{ fill: CHART_INK.label, fontSize: 11, fontVariantNumeric: "tabular-nums" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Repair completion rate per month (single series). */
export function CompletionRateChart({ data }: { data: MonthlyTrendPoint[] }) {
  const animate = !useReducedMotion();
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ left: -16, right: 8, top: 6, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="label" {...axisProps} />
          <YAxis
            {...axisProps}
            axisLine={false}
            tickFormatter={(v: number) => formatPercent(v)}
            domain={[0, 1]}
          />
          <Tooltip content={<DefaultTooltip formatter={(v) => formatPercent(v, 1)} />} />
          <Area
            type="monotone"
            dataKey="completionRate"
            name="Completion rate"
            stroke={SERIES.blue}
            strokeWidth={2}
            fill={SERIES.blue}
            fillOpacity={0.12}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
            isAnimationActive={animate}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Estimated backlog cost by district (single measure, one hue). */
export function BacklogCostChart({ data }: { data: DistrictReportRow[] }) {
  const animate = !useReducedMotion();
  const rows = data.map((d) => ({
    name: districtById(d.district).name,
    cost: d.backlogCost,
  }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 48, top: 4, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={110} {...axisProps} axisLine={false} />
          <Tooltip
            cursor={{ fill: CHART_INK.grid, opacity: 0.4 }}
            content={<DefaultTooltip formatter={(v) => formatCurrencyCompact(v)} />}
          />
          <Bar dataKey="cost" name="Backlog" barSize={14} radius={[0, 4, 4, 0]} fill={SERIES.blue} isAnimationActive={animate}>
            <LabelList
              dataKey="cost"
              position="right"
              formatter={(v: number) => formatCurrencyCompact(v)}
              style={{ fill: CHART_INK.label, fontSize: 11, fontVariantNumeric: "tabular-nums" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
