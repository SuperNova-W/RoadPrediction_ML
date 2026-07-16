"use client";

import * as React from "react";
import {
  CircleDollarSign,
  FileDown,
  Landmark,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { AnimatedNumber } from "@/components/domain/animated-number";
import { GradeChip, SeverityBadge } from "@/components/domain/badges";
import { BacklogTrendChart, ResponseTimeChart } from "@/components/charts/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getExecutiveSummary, getRoadSegments } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { DISTRICTS } from "@/lib/mock/districts";
import { gradeForScore } from "@/lib/mock/government";
import { formatCurrencyCompact } from "@/lib/format";

export default function ExecutivePage() {
  const summary = useAsync(() => getExecutiveSummary(), []);
  const segments = useAsync(() => getRoadSegments(), []);

  const districtScorecard = React.useMemo(() => {
    if (!segments.data) return [];
    return DISTRICTS.map((district) => {
      const rows = segments.data!.filter((s) => s.district === district.id);
      const miles = rows.reduce((sum, s) => sum + s.lengthMiles, 0);
      const avg =
        rows.reduce((sum, s) => sum + s.conditionScore * s.lengthMiles, 0) /
        Math.max(miles, 0.1);
      return {
        district: district.id,
        name: district.name,
        avgScore: Math.round(avg),
        grade: gradeForScore(avg),
        openIssues: rows.reduce((sum, s) => sum + s.openIssues, 0),
        worst: rows[0]?.streetName ?? "—",
      };
    }).sort((a, b) => a.avgScore - b.avgScore);
  }, [segments.data]);

  const budget = summary.data?.budget;
  const committedPct = budget ? (budget.committed / budget.allocated) * 100 : 0;
  const spentPct = budget ? (budget.spent / budget.allocated) * 100 : 0;

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Executive brief"
        description="Quarterly summary for leadership and council. All figures are fictional demo data."
        actions={
          <Button
            variant="outline"
            onClick={() =>
              toast.info("Council packet export is demo-only", {
                description:
                  "In production this produces a signed PDF summary. Use Reports → Export CSV for raw data.",
              })
            }
          >
            <FileDown aria-hidden /> Export council packet
          </Button>
        }
      />

      {/* Headline tiles */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Landmark className="h-3.5 w-3.5" aria-hidden /> Network condition
            </p>
            {summary.loading ? (
              <Skeleton className="mt-2 h-8 w-24" />
            ) : (
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="tnum text-3xl font-semibold tracking-tight">
                  <AnimatedNumber value={summary.data?.conditionScore ?? 0} />
                </span>
                <span className="text-lg font-semibold text-muted-foreground">
                  / 100 · {gradeForScore(summary.data?.conditionScore ?? 0)}
                </span>
              </div>
            )}
            <p className="mt-1 flex items-center gap-1 text-xs text-success">
              <TrendingUp className="h-3.5 w-3.5" aria-hidden />+
              {summary.data?.conditionDelta ?? 0} pts vs last quarter
            </p>
          </CardContent>
        </Card>

        <Card className="sm:col-span-1 xl:col-span-2">
          <CardContent className="p-4">
            <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <CircleDollarSign className="h-3.5 w-3.5" aria-hidden />
              {budget?.fiscalYear ?? "FY"} maintenance budget
            </p>
            {summary.loading || !budget ? (
              <Skeleton className="mt-2 h-16 w-full" />
            ) : (
              <div className="mt-2 space-y-2">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="tnum text-2xl font-semibold tracking-tight">
                    {formatCurrencyCompact(budget.allocated)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    <span className="tnum">{formatCurrencyCompact(budget.spent)}</span> spent ·{" "}
                    <span className="tnum">{formatCurrencyCompact(budget.committed)}</span> committed
                  </span>
                </div>
                <div className="relative">
                  <Progress value={committedPct} className="h-2.5" indicatorClassName="bg-primary/30" aria-label="Committed budget" />
                  <div className="absolute inset-0">
                    <Progress value={spentPct} className="h-2.5 bg-transparent" aria-label="Spent budget" />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  <span className="inline-block h-2 w-2 rounded-full bg-primary align-middle" />{" "}
                  Spent · <span className="inline-block h-2 w-2 rounded-full bg-primary/30 align-middle" />{" "}
                  Committed (approved &amp; scheduled work)
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <TrendingDown className="h-3.5 w-3.5" aria-hidden /> Est. repair backlog
            </p>
            {summary.loading ? (
              <Skeleton className="mt-2 h-8 w-24" />
            ) : (
              <p className="tnum mt-1.5 text-3xl font-semibold tracking-tight">
                <AnimatedNumber
                  value={summary.data?.backlogTrend.at(-1)?.backlog ?? 0}
                  format={formatCurrencyCompact}
                />
              </p>
            )}
            <p className="mt-1 text-xs text-success">Down 19% from March peak</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2 [&>*]:min-w-0">
        <Card>
          <CardHeader>
            <CardTitle>Backlog trend</CardTitle>
            <CardDescription>Estimated cost of open, confirmed repairs by month</CardDescription>
          </CardHeader>
          <CardContent>
            {summary.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <BacklogTrendChart data={summary.data?.backlogTrend ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Response times</CardTitle>
            <CardDescription>
              Median days from detection to human review and to completed repair
            </CardDescription>
          </CardHeader>
          <CardContent>
            {summary.loading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <ResponseTimeChart data={summary.data?.response ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>District scorecard</CardTitle>
              <CardDescription>Length-weighted condition by district, worst first</CardDescription>
            </div>
            <Badge variant="muted">Mock data</Badge>
          </CardHeader>
          <CardContent className="px-0 pb-2">
            {segments.loading ? (
              <Skeleton className="mx-5 h-48 w-auto" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-5">District</TableHead>
                    <TableHead>Grade</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="hidden text-right sm:table-cell">Open issues</TableHead>
                    <TableHead className="hidden pr-5 md:table-cell">Weakest segment</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {districtScorecard.map((row) => (
                    <TableRow key={row.district}>
                      <TableCell className="pl-5 font-medium">{row.name}</TableCell>
                      <TableCell>
                        <GradeChip grade={row.grade} />
                      </TableCell>
                      <TableCell className="tnum text-right">{row.avgScore}</TableCell>
                      <TableCell className="tnum hidden text-right sm:table-cell">
                        {row.openIssues}
                      </TableCell>
                      <TableCell className="hidden pr-5 text-sm text-muted-foreground md:table-cell">
                        {row.worst}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted-foreground" aria-hidden />
              Quarter highlights
            </CardTitle>
            <CardDescription>Talking points generated from the demo dataset</CardDescription>
          </CardHeader>
          <CardContent>
            {summary.loading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <ul className="space-y-3">
                {(summary.data?.highlights ?? []).map((highlight, i) => (
                  <li key={i} className="flex gap-2.5 text-sm leading-relaxed">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                    {highlight}
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-4 flex flex-wrap gap-2 border-t pt-3 text-xs text-muted-foreground">
              <span>Severity legend:</span>
              <SeverityBadge severity="severe" />
              <SeverityBadge severity="high" />
              <SeverityBadge severity="moderate" />
              <SeverityBadge severity="low" />
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
              Condition scores and response medians are planning heuristics from
              image evidence — not certified PCI values or an engineering assessment.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
