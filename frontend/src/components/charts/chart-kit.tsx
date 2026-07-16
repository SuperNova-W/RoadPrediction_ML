"use client";

import type { TooltipProps } from "recharts";
import { CHART_INK } from "@/lib/tokens";

/** Shared axis styling: recessive grid/axes, muted tabular labels. */
export const axisProps = {
  stroke: CHART_INK.baseline,
  tick: { fill: CHART_INK.axis, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: CHART_INK.baseline },
} as const;

export const gridProps = {
  stroke: CHART_INK.grid,
  vertical: false,
} as const;

interface TooltipRow {
  name: string;
  value: string;
  color?: string;
}

export function ChartTooltipCard({
  title,
  rows,
}: {
  title?: string;
  rows: TooltipRow[];
}) {
  return (
    <div className="rounded-md border bg-card px-3 py-2 text-xs shadow-overlay">
      {title ? <p className="mb-1 font-medium text-foreground">{title}</p> : null}
      <div className="space-y-0.5">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              {r.color ? (
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: r.color }}
                  aria-hidden
                />
              ) : null}
              {r.name}
            </span>
            <span className="tnum font-medium text-foreground">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Generic recharts tooltip adapter. */
export function DefaultTooltip({
  active,
  payload,
  label,
  formatter = (v) => String(v),
}: TooltipProps<number, string> & { formatter?: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <ChartTooltipCard
      title={label != null ? String(label) : undefined}
      rows={payload.map((p) => ({
        name: String(p.name),
        value: formatter(Number(p.value)),
        color: (p.color as string) ?? undefined,
      }))}
    />
  );
}

/** Simple legend rendered in ink tokens (color chip carries identity). */
export function ChartLegend({
  items,
}: {
  items: { label: string; color: string }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: it.color }}
            aria-hidden
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}
