"use client";

import * as React from "react";
import { FileDown, FileSpreadsheet, Info } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import {
  BacklogCostChart,
  ClassTrendsChart,
  CompletionRateChart,
  DistrictComparisonChart,
  PriorityDistributionChart,
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDistrictReport, getIssues, getTrends } from "@/lib/api";
import { DAMAGE_CLASSES } from "@/lib/types";
import { useAsync } from "@/lib/hooks/use-async";
import { districtById } from "@/lib/mock/districts";
import { formatCurrency } from "@/lib/format";

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const csv = [headers, ...rows]
    .map((row) =>
      row
        .map((cell) => {
          const s = String(cell);
          return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        })
        .join(","),
    )
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const trends = useAsync(() => getTrends(), []);
  const districtReport = useAsync(() => getDistrictReport(), []);
  const issues = useAsync(() => getIssues(), []);

  const priorityBuckets = React.useMemo(() => {
    const buckets = [
      { bucket: "0–39", count: 0 },
      { bucket: "40–59", count: 0 },
      { bucket: "60–79", count: 0 },
      { bucket: "80+", count: 0 },
    ];
    for (const issue of issues.data ?? []) {
      const s = issue.priorityScore;
      buckets[s >= 80 ? 3 : s >= 60 ? 2 : s >= 40 ? 1 : 0].count++;
    }
    return buckets;
  }, [issues.data]);

  const exportIssuesCsv = () => {
    if (!issues.data) return;
    downloadCsv(
      "roadlens-demo-issues.csv",
      ["id", "road", "district", "damage_type", "confidence", "severity", "priority", "review_status", "captured_at", "lng", "lat"],
      issues.data.map((i) => [
        i.id, i.roadName, i.district, DAMAGE_CLASSES[i.classCode].label, i.confidence, i.severity,
        i.priorityScore, i.reviewStatus, i.capturedAt, i.coordinates[0], i.coordinates[1],
      ]),
    );
    toast.success("CSV downloaded", { description: "Contains the demo mock dataset." });
  };

  const exportPdf = () => {
    toast.info("PDF export is demo-only", {
      description:
        "In production this generates a signed municipal report. The prototype exports CSV only.",
    });
  };

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Reports"
        description="District comparisons, trends, and exports."
        actions={
          <>
            <Button variant="outline" onClick={exportIssuesCsv}>
              <FileSpreadsheet aria-hidden /> Export CSV
            </Button>
            <Button variant="outline" onClick={exportPdf}>
              <FileDown aria-hidden /> Export PDF
            </Button>
          </>
        }
      />

      <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3 text-sm">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
        <p>
          <strong>Mock report data.</strong> Every figure on this page is
          fictional demo data for the City of Meridian Falls and does not
          represent measured results from any municipality.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2 [&>*]:min-w-0">
        <Card>
          <CardHeader>
            <CardTitle>District comparison</CardTitle>
            <CardDescription>Open issues by damage type per district</CardDescription>
          </CardHeader>
          <CardContent>
            {districtReport.loading ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <DistrictComparisonChart data={districtReport.data ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Damage-type trends</CardTitle>
            <CardDescription>Monthly detections by damage type, last 12 months</CardDescription>
          </CardHeader>
          <CardContent>
            {trends.loading ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <ClassTrendsChart data={trends.data ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Priority distribution</CardTitle>
            <CardDescription>Open issues by repair-priority band</CardDescription>
          </CardHeader>
          <CardContent>
            {issues.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <PriorityDistributionChart data={priorityBuckets} />
            )}
          </CardContent>
        </Card>

        <Card>
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
              <CompletionRateChart data={trends.data ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Estimated backlog by district</CardTitle>
            <CardDescription>Planning estimates, not engineering quotes</CardDescription>
          </CardHeader>
          <CardContent>
            {districtReport.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <BacklogCostChart data={districtReport.data ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>District summary table</CardTitle>
              <CardDescription>The data behind the charts</CardDescription>
            </div>
            <Badge variant="muted">Mock data</Badge>
          </CardHeader>
          <CardContent className="px-0 pb-2">
            {districtReport.loading ? (
              <Skeleton className="mx-5 h-48 w-auto" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-5">District</TableHead>
                    <TableHead className="text-right">Open</TableHead>
                    <TableHead className="text-right">Resolved (90d)</TableHead>
                    <TableHead className="text-right">Avg. priority</TableHead>
                    <TableHead className="pr-5 text-right">Backlog est.</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(districtReport.data ?? []).map((row) => (
                    <TableRow key={row.district}>
                      <TableCell className="pl-5 font-medium">
                        {districtById(row.district).name}
                      </TableCell>
                      <TableCell className="tnum text-right">{row.open}</TableCell>
                      <TableCell className="tnum text-right">{row.resolved90d}</TableCell>
                      <TableCell className="tnum text-right">{row.avgPriority}</TableCell>
                      <TableCell className="tnum pr-5 text-right">
                        {formatCurrency(row.backlogCost)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
