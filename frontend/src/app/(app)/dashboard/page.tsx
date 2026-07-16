"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Camera,
  CircleDollarSign,
  Gauge,
  ListChecks,
  Route,
  ScanSearch,
  TruckIcon,
} from "lucide-react";
import { PageHeader } from "@/components/app/page-header";
import { AnimatedNumber } from "@/components/domain/animated-number";
import { ClassBadge, PriorityScore, SeverityBadge } from "@/components/domain/badges";
import { DamageDistributionChart, DetectionTrendChart } from "@/components/charts/charts";
import { IssueMap } from "@/components/map/issue-map";
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
import { MunicipalitySwitcher } from "@/components/app/municipality-switcher";
import {
  getDashboardStats,
  getDistricts,
  getIssues,
  getRecentActivity,
  getTrends,
  getVehicles,
} from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { MOCK_NOW } from "@/lib/mock/seed";
import type { DamageClassCode } from "@/lib/types";
import {
  formatCurrencyCompact,
  formatNumber,
  formatPercent,
  formatRelative,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const RANGES = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

function StatCard({
  label,
  icon: Icon,
  value,
  detail,
  tone,
  loading,
}: {
  label: string;
  icon: React.ElementType;
  value: React.ReactNode;
  detail: string;
  tone?: "danger" | "default";
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon
            className={cn("h-3.5 w-3.5", tone === "danger" && "text-destructive")}
            aria-hidden
          />
          {label}
        </div>
        {loading ? (
          <Skeleton className="mt-2 h-7 w-20" />
        ) : (
          <p
            className={cn(
              "tnum mt-1.5 text-2xl font-semibold tracking-tight",
              tone === "danger" && "text-destructive",
            )}
          >
            {value}
          </p>
        )}
        <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [range, setRange] = React.useState("30");
  const capturedAfter = new Date(
    MOCK_NOW - Number(range) * 86400_000,
  ).toISOString();

  const stats = useAsync(() => getDashboardStats(), []);
  const trends = useAsync(() => getTrends(), []);
  const issues = useAsync(() => getIssues({ capturedAfter }), [capturedAfter]);
  const activity = useAsync(() => getRecentActivity(), []);
  const vehicles = useAsync(() => getVehicles(), []);
  const districts = useAsync(() => getDistricts(), []);

  const distribution = React.useMemo(() => {
    const counts: Record<DamageClassCode, number> = { D00: 0, D10: 0, D20: 0, D40: 0 };
    for (const issue of issues.data ?? []) counts[issue.classCode]++;
    return (Object.keys(counts) as DamageClassCode[]).map((code) => ({
      code,
      count: counts[code],
    }));
  }, [issues.data]);

  const recent = (issues.data ?? []).slice(0, 6);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <PageHeader
        title="Overview"
        description="Network health for the selected period. All data in this demo is mock data."
        actions={
          <>
            <div className="w-56">
              <MunicipalitySwitcher />
            </div>
            <Select value={range} onValueChange={setRange}>
              <SelectTrigger className="w-36" aria-label="Date range">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RANGES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <StatCard
          label="Network coverage"
          icon={Gauge}
          loading={stats.loading}
          value={
            stats.data ? (
              <AnimatedNumber
                value={stats.data.coveragePct * 100}
                format={(v) => `${v.toFixed(0)}%`}
              />
            ) : null
          }
          detail={
            stats.data
              ? `+${formatPercent(stats.data.coverageDeltaPct)} vs prior period`
              : "—"
          }
        />
        <StatCard
          label="Open issues"
          icon={ListChecks}
          loading={stats.loading}
          value={stats.data ? <AnimatedNumber value={stats.data.openIssues} /> : null}
          detail="Awaiting review or repair"
        />
        <StatCard
          label="Urgent issues"
          icon={AlertTriangle}
          tone="danger"
          loading={stats.loading}
          value={stats.data ? <AnimatedNumber value={stats.data.urgentIssues} /> : null}
          detail="Severe or priority ≥ 80"
        />
        <StatCard
          label="Miles analyzed"
          icon={Route}
          loading={stats.loading}
          value={
            stats.data ? (
              <AnimatedNumber value={stats.data.milesAnalyzed} format={formatNumber} />
            ) : null
          }
          detail="Lane-miles with recent imagery"
        />
        <StatCard
          label="Est. repair backlog"
          icon={CircleDollarSign}
          loading={stats.loading}
          value={
            stats.data ? (
              <AnimatedNumber
                value={stats.data.backlogEstimate}
                format={formatCurrencyCompact}
              />
            ) : null
          }
          detail="Planning estimate, not a quote"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        {/* Map */}
        <Card className="xl:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>City map</CardTitle>
              <CardDescription>
                Detections in the selected period, clustered by proximity
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/map">
                Open full map <ArrowRight aria-hidden />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="h-[360px] pb-5">
            {issues.loading || districts.loading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <IssueMap
                issues={issues.data ?? []}
                districts={districts.data ?? []}
                showDistricts
                onSelect={(id) => id && router.push(`/issues/${id}`)}
              />
            )}
          </CardContent>
        </Card>

        {/* Damage distribution + trend */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Damage distribution</CardTitle>
              <CardDescription>Open issues by damage type, selected period</CardDescription>
            </CardHeader>
            <CardContent>
              {issues.loading ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <DamageDistributionChart data={distribution} />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Priority trend</CardTitle>
              <CardDescription>New detections vs. resolved, by month</CardDescription>
            </CardHeader>
            <CardContent>
              {trends.loading ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <DetectionTrendChart data={trends.data ?? []} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        {/* Recent detections */}
        <Card className="xl:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>Recent detections</CardTitle>
              <CardDescription>Highest-priority detections in the period</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/issues">
                View all <ArrowUpRight aria-hidden />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="px-2 pb-3">
            {issues.loading ? (
              <div className="space-y-2 px-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : (
              <ul className="divide-y">
                {recent.map((issue) => (
                  <li key={issue.id}>
                    <Link
                      href={`/issues/${issue.id}`}
                      className="flex items-center gap-3 rounded-md px-3 py-2.5 outline-none transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <ScanSearch className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          <span className="tnum">{issue.id}</span> · {issue.roadName}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatRelative(issue.capturedAt)} · {issue.vehicleId}
                        </p>
                      </div>
                      <div className="hidden sm:block">
                        <ClassBadge code={issue.classCode} short />
                      </div>
                      <div className="hidden min-[420px]:block">
                        <SeverityBadge severity={issue.severity} />
                      </div>
                      <PriorityScore score={issue.priorityScore} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Fleet + activity */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TruckIcon className="h-4 w-4 text-muted-foreground" aria-hidden />
                Fleet ingestion
              </CardTitle>
              <CardDescription>Capture vehicles reporting today</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {vehicles.loading ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                (vehicles.data ?? []).map((v) => (
                  <div key={v.id} className="flex items-center gap-3">
                    <Camera className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{v.name}</p>
                      <p className="tnum text-xs text-muted-foreground">
                        {v.imagesToday.toLocaleString()} images · {v.milesToday} mi today
                      </p>
                    </div>
                    <Badge
                      variant={
                        v.status === "active"
                          ? "success"
                          : v.status === "idle"
                            ? "warning"
                            : "muted"
                      }
                    >
                      {v.status}
                    </Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" aria-hidden />
                Recent activity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {activity.loading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                (activity.data ?? []).slice(0, 5).map((event) => (
                  <div key={event.id} className="flex gap-2 text-sm">
                    <span
                      className={cn(
                        "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                        event.actorIsSystem ? "bg-primary" : "bg-success",
                      )}
                      aria-hidden
                    />
                    <div>
                      <p className="leading-snug">{event.message}</p>
                      <p className="text-xs text-muted-foreground">
                        {event.actor} · {formatRelative(event.timestamp)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
