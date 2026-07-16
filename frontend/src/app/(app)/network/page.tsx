"use client";

import * as React from "react";
import {
  ArrowDown,
  ArrowUp,
  Minus,
  SearchX,
  Waypoints,
} from "lucide-react";
import { PageHeader } from "@/components/app/page-header";
import { GradeChip } from "@/components/domain/badges";
import { ConditionDistributionChart } from "@/components/charts/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
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
import { getRoadSegments } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { districtById, DISTRICTS } from "@/lib/mock/districts";
import type { ConditionGrade, ConditionTrend } from "@/lib/types";
import { formatRelative } from "@/lib/format";

const GRADES: ConditionGrade[] = ["A", "B", "C", "D", "F"];

const TREND_META: Record<ConditionTrend, { icon: React.ElementType; className: string; label: string }> = {
  improving: { icon: ArrowUp, className: "text-success", label: "Improving" },
  stable: { icon: Minus, className: "text-muted-foreground", label: "Stable" },
  declining: { icon: ArrowDown, className: "text-destructive", label: "Declining" },
};

export default function NetworkPage() {
  const segments = useAsync(() => getRoadSegments(), []);
  const [search, setSearch] = React.useState("");
  const [districtId, setDistrictId] = React.useState("all");
  const [grade, setGrade] = React.useState("all");

  const rows = React.useMemo(() => {
    let list = segments.data ?? [];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) => s.streetName.toLowerCase().includes(q) || s.id.toLowerCase().includes(q),
      );
    }
    if (districtId !== "all") list = list.filter((s) => s.district === districtId);
    if (grade !== "all") list = list.filter((s) => s.grade === grade);
    return list;
  }, [segments.data, search, districtId, grade]);

  const distribution = React.useMemo(() => {
    const byGrade: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 };
    for (const s of segments.data ?? []) byGrade[s.grade] += s.lengthMiles;
    return GRADES.map((g) => ({ grade: g, miles: Math.round(byGrade[g] * 10) / 10 }));
  }, [segments.data]);

  const totals = React.useMemo(() => {
    const list = segments.data ?? [];
    const miles = list.reduce((sum, s) => sum + s.lengthMiles, 0);
    const poor = list.filter((s) => s.grade === "D" || s.grade === "F");
    return {
      segments: list.length,
      miles: Math.round(miles * 10) / 10,
      poorMiles: Math.round(poor.reduce((sum, s) => sum + s.lengthMiles, 0) * 10) / 10,
      declining: list.filter((s) => s.trend === "declining").length,
    };
  }, [segments.data]);

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Road network"
        description="Street-segment condition from repeated fleet passes. Scores are heuristics, not certified PCI values. Mock data."
      />

      <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Waypoints className="h-4 w-4 text-muted-foreground" aria-hidden />
              Condition distribution
            </CardTitle>
            <CardDescription>Monitored lane-miles by condition grade</CardDescription>
          </CardHeader>
          <CardContent>
            {segments.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <ConditionDistributionChart data={distribution} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Network at a glance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {segments.loading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <>
                <Stat label="Monitored segments" value={String(totals.segments)} />
                <Stat label="Monitored lane-miles" value={`${totals.miles} mi`} />
                <Stat
                  label="Miles graded D or F"
                  value={`${totals.poorMiles} mi`}
                  tone="danger"
                />
                <Stat
                  label="Segments trending down"
                  value={String(totals.declining)}
                  tone="danger"
                />
                <p className="border-t pt-3 text-[11px] leading-relaxed text-muted-foreground">
                  Grades weight recent detections by severity and density per
                  segment. They prioritize attention — they do not replace a
                  licensed pavement survey.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search street or segment…"
          className="w-full sm:w-64"
          aria-label="Search segments"
        />
        <Select value={districtId} onValueChange={setDistrictId}>
          <SelectTrigger className="w-44" aria-label="Filter by district">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All districts</SelectItem>
            {DISTRICTS.map((d) => (
              <SelectItem key={d.id} value={d.id}>
                {d.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={grade} onValueChange={setGrade}>
          <SelectTrigger className="w-36" aria-label="Filter by grade">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All grades</SelectItem>
            {GRADES.map((g) => (
              <SelectItem key={g} value={g}>
                Grade {g}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {segments.loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No segments match"
          description="Try a different district or grade filter."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearch("");
                setDistrictId("all");
                setGrade("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Segment</TableHead>
                <TableHead>Grade</TableHead>
                <TableHead className="hidden sm:table-cell">Condition</TableHead>
                <TableHead className="hidden md:table-cell">Trend</TableHead>
                <TableHead className="hidden text-right lg:table-cell">Length</TableHead>
                <TableHead className="text-right">Open issues</TableHead>
                <TableHead className="hidden pr-4 text-right sm:table-cell">
                  Last imaged
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((segment) => {
                const trend = TREND_META[segment.trend];
                return (
                  <TableRow key={segment.id}>
                    <TableCell className="pl-4">
                      <p className="font-medium">{segment.streetName}</p>
                      <p className="tnum text-xs text-muted-foreground">
                        {segment.id} · {districtById(segment.district).name}
                      </p>
                    </TableCell>
                    <TableCell>
                      <GradeChip grade={segment.grade} />
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-1.5 w-24 overflow-hidden rounded-full bg-secondary"
                          role="img"
                          aria-label={`Condition score ${segment.conditionScore} of 100`}
                        >
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${segment.conditionScore}%` }}
                          />
                        </div>
                        <span className="tnum text-sm text-muted-foreground">
                          {segment.conditionScore}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <span className={`flex items-center gap-1 text-sm ${trend.className}`}>
                        <trend.icon className="h-3.5 w-3.5" aria-hidden />
                        {trend.label}
                      </span>
                    </TableCell>
                    <TableCell className="tnum hidden text-right text-sm lg:table-cell">
                      {segment.lengthMiles} mi
                    </TableCell>
                    <TableCell className="text-right">
                      {segment.openIssues > 0 ? (
                        <Badge variant={segment.openIssues >= 4 ? "destructive" : "secondary"}>
                          {segment.openIssues}
                        </Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell className="hidden pr-4 text-right text-sm text-muted-foreground sm:table-cell">
                      {formatRelative(segment.lastInspected)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "danger";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span
        className={`tnum text-lg font-semibold ${tone === "danger" ? "text-destructive" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
