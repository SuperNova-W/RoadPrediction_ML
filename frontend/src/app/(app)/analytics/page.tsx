"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  Database,
  FileDown,
  FileSpreadsheet,
  Info,
  Scale,
  TriangleAlert,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { ClassBadge, PriorityScore, SeverityBadge } from "@/components/domain/badges";
import {
  ClassTrendsChart,
  CompletionRateChart,
  DistrictSnapshotChart,
  PeerBenchmarkChart,
  PriorityDistributionChart,
  Sparkline,
} from "@/components/charts/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  getDistricts,
  getIssues,
  getPeerBenchmark,
  getPerformanceMeasures,
  getTrends,
} from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { districtById } from "@/lib/mock/districts";
import type { MeasureStatus, PerformanceMeasure } from "@/lib/types";
import {
  formatCurrency,
  formatDateTime,
  formatPercent,
} from "@/lib/format";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Measure formatting + status chips                                   */
/* ------------------------------------------------------------------ */

function formatMeasureValue(m: PerformanceMeasure, v: number): string {
  switch (m.format) {
    case "percent":
      return formatPercent(v);
    case "days":
      return `${v} days`;
    case "score":
      return `${v} / 100`;
    case "currency":
      return `$${v.toLocaleString()}`;
  }
}

const STATUS_META: Record<
  MeasureStatus,
  { label: string; icon: React.ElementType; className: string }
> = {
  on_track: {
    label: "On track",
    icon: CheckCircle2,
    className: "border-success/25 bg-success/10 text-success",
  },
  watch: {
    label: "Watch",
    icon: CircleAlert,
    className: "border-warning/25 bg-warning/10 text-warning",
  },
  off_track: {
    label: "Off track",
    icon: TriangleAlert,
    className: "border-destructive/25 bg-destructive/10 text-destructive",
  },
};

function MeasureCard({ measure }: { measure: PerformanceMeasure }) {
  const status = STATUS_META[measure.status];
  const StatusIcon = status.icon;
  const DeltaIcon = measure.yoyIsImprovement ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className="flex flex-col">
      <CardContent className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium leading-snug">{measure.name}</p>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                className="rounded-full text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`Why we track: ${measure.name}`}
              >
                <Info className="h-3.5 w-3.5" aria-hidden />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-64">
              {measure.whyItMatters}
            </TooltipContent>
          </Tooltip>
        </div>

        <div className="mt-2 flex items-baseline gap-2">
          <span className="tnum text-2xl font-semibold tracking-tight">
            {formatMeasureValue(measure, measure.value)}
          </span>
          {measure.unitSuffix ? (
            <span className="text-xs text-muted-foreground">{measure.unitSuffix}</span>
          ) : null}
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
              status.className,
            )}
          >
            <StatusIcon className="h-3 w-3" aria-hidden />
            {status.label}
          </span>
          <span className="text-xs text-muted-foreground">
            Target {measure.direction === "at_or_above" ? "≥" : "≤"}{" "}
            {formatMeasureValue(measure, measure.target)}
          </span>
        </div>

        <Sparkline data={measure.spark} good={measure.yoyIsImprovement} />

        <p
          className={cn(
            "flex items-center gap-1 text-xs font-medium",
            measure.yoyIsImprovement ? "text-success" : "text-destructive",
          )}
        >
          <DeltaIcon className="h-3.5 w-3.5" aria-hidden />
          {measure.yoyDelta}
        </p>
        <p className="mt-2 border-t pt-2 text-[11px] leading-snug text-muted-foreground">
          <CalendarClock className="mr-1 inline h-3 w-3 align-[-2px]" aria-hidden />
          {measure.periodLabel} · {measure.updatedNote}
        </p>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

const RANGE_OPTIONS = [
  { value: "12", label: "Last 12 months" },
  { value: "6", label: "Last 6 months" },
  { value: "3", label: "Last 3 months" },
];

export default function AnalyticsPage() {
  const measures = useAsync(() => getPerformanceMeasures(), []);
  const trends = useAsync(() => getTrends(), []);
  const issues = useAsync(() => getIssues(), []);
  const districts = useAsync(() => getDistricts(), []);
  const benchmark = useAsync(() => getPeerBenchmark(), []);

  const [range, setRange] = React.useState("12");
  const [districtFilter, setDistrictFilter] = React.useState<string | null>(null);

  const trendSlice = (trends.data ?? []).slice(-Number(range));

  const filteredIssues = React.useMemo(() => {
    let rows = (issues.data ?? []).filter((i) => i.reviewStatus !== "rejected");
    if (districtFilter) rows = rows.filter((i) => i.district === districtFilter);
    return rows;
  }, [issues.data, districtFilter]);

  const snapshot = React.useMemo(() => {
    return (districts.data ?? []).map((d) => ({
      id: d.id,
      name: d.name,
      count: (issues.data ?? []).filter(
        (i) => i.district === d.id && i.reviewStatus !== "rejected",
      ).length,
    }));
  }, [districts.data, issues.data]);

  const priorityBuckets = React.useMemo(() => {
    const buckets = [
      { bucket: "0–39", count: 0 },
      { bucket: "40–59", count: 0 },
      { bucket: "60–79", count: 0 },
      { bucket: "80+", count: 0 },
    ];
    for (const issue of filteredIssues) {
      const s = issue.priorityScore;
      buckets[s >= 80 ? 3 : s >= 60 ? 2 : s >= 40 ? 1 : 0].count++;
    }
    return buckets;
  }, [filteredIssues]);

  const exportCsv = () => {
    const rows = filteredIssues;
    const csv = [
      ["id", "road", "district", "damage_type", "severity", "priority", "captured_at"],
      ...rows.map((i) => [
        i.id,
        i.roadName,
        districtById(i.district).name,
        i.classCode,
        i.severity,
        i.priorityScore,
        i.capturedAt,
      ]),
    ]
      .map((r) => r.join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "roadlens-analytics-demo.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV downloaded", { description: "Contains the demo mock dataset." });
  };

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Analytics"
        description="Performance measures with targets, drill-downs, and peer benchmarking. Mock data throughout."
        actions={
          <>
            <Select value={range} onValueChange={setRange}>
              <SelectTrigger className="w-40" aria-label="Time range">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RANGE_OPTIONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={exportCsv}>
              <FileSpreadsheet aria-hidden /> CSV
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                toast.info("PDF export is demo-only", {
                  description: "In production this produces a signed report packet.",
                })
              }
            >
              <FileDown aria-hidden /> PDF
            </Button>
          </>
        }
      />

      {/* Measure cards */}
      <section aria-label="Performance measures">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
          {measures.loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-56 w-full" />
              ))
            : (measures.data ?? []).map((measure) => (
                <MeasureCard key={measure.id} measure={measure} />
              ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        {/* Drill-down explorer */}
        <Card className="xl:col-span-2">
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0">
            <div>
              <CardTitle>Open issues — explore</CardTitle>
              <CardDescription>
                Click a district bar to drill into its records
              </CardDescription>
            </div>
            {districtFilter ? (
              <Badge variant="secondary" className="gap-1 pr-1">
                {districtById(districtFilter).name}
                <button
                  onClick={() => setDistrictFilter(null)}
                  className="rounded-full p-0.5 hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Clear district filter"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </Badge>
            ) : null}
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="snapshot">
              <TabsList aria-label="Analysis views" className="h-auto flex-wrap">
                <TabsTrigger value="snapshot">Snapshot</TabsTrigger>
                <TabsTrigger value="overtime">Over time</TabsTrigger>
                <TabsTrigger value="distribution">Distribution</TabsTrigger>
                <TabsTrigger value="records">Records</TabsTrigger>
              </TabsList>

              <TabsContent value="snapshot">
                {issues.loading || districts.loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : (
                  <DistrictSnapshotChart
                    data={snapshot}
                    selected={districtFilter}
                    onSelect={setDistrictFilter}
                  />
                )}
              </TabsContent>

              <TabsContent value="overtime">
                {trends.loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : (
                  <ClassTrendsChart data={trendSlice} />
                )}
              </TabsContent>

              <TabsContent value="distribution">
                {issues.loading ? (
                  <Skeleton className="h-56 w-full" />
                ) : (
                  <PriorityDistributionChart data={priorityBuckets} />
                )}
              </TabsContent>

              <TabsContent value="records">
                {issues.loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : filteredIssues.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    No open issues match the current filter.
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Issue</TableHead>
                        <TableHead className="hidden sm:table-cell">Type</TableHead>
                        <TableHead className="hidden md:table-cell">Severity</TableHead>
                        <TableHead className="text-right">Priority</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredIssues.slice(0, 8).map((issue) => (
                        <TableRow key={issue.id}>
                          <TableCell>
                            <Link
                              href={`/issues/${issue.id}`}
                              className="rounded outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              <span className="tnum font-medium">{issue.id}</span>
                              <span className="block text-xs text-muted-foreground">
                                {issue.roadName} · {formatDateTime(issue.capturedAt)}
                              </span>
                            </Link>
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            <ClassBadge code={issue.classCode} short />
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            <SeverityBadge severity={issue.severity} />
                          </TableCell>
                          <TableCell className="text-right">
                            <PriorityScore score={issue.priorityScore} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Peer benchmarking */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-muted-foreground" aria-hidden />
              Peer benchmark
            </CardTitle>
            <CardDescription>
              {benchmark.data?.measureLabel ?? "Backlog per lane-mile"}, lower is better
            </CardDescription>
          </CardHeader>
          <CardContent>
            {benchmark.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <>
                <PeerBenchmarkChart
                  rows={benchmark.data?.rows ?? []}
                  formatter={(v) => formatCurrency(v)}
                />
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  {benchmark.data?.cohortNote}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Completion rate */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Repair completion rate</CardTitle>
            <CardDescription>
              Share of confirmed issues repaired within the month
            </CardDescription>
          </CardHeader>
          <CardContent>
            {trends.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <CompletionRateChart data={trendSlice} />
            )}
          </CardContent>
        </Card>

        {/* About this data */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-4 w-4 text-muted-foreground" aria-hidden />
              About this data
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              <strong className="text-foreground">Source.</strong> Fleet-camera
              detections confirmed by city reviewers, work-order records, and
              citizen reports. Rejected detections are excluded from all measures.
            </p>
            <p>
              <strong className="text-foreground">Cadence.</strong> Operational
              measures refresh nightly; condition scores weekly; reporting
              periods close quarterly.
            </p>
            <p>
              <strong className="text-foreground">Method.</strong> Severity,
              condition, and priority values are planning heuristics derived
              from image evidence — not certified PCI surveys or engineering
              assessments.
            </p>
            <Badge variant="muted">Demo workspace — all figures fictional</Badge>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
