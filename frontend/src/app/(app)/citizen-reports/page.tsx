"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowUpRight,
  CheckCircle2,
  ClipboardPlus,
  ImageOff,
  Inbox,
  Link2,
  MapPin,
  Megaphone,
  Phone,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { ClassBadge, PriorityScore } from "@/components/domain/badges";
import { RoadImage } from "@/components/domain/road-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createWorkOrder,
  getCitizenReports,
  matchCitizenReport,
  setCitizenReportStatus,
  suggestMatches,
} from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { districtById } from "@/lib/mock/districts";
import type { CitizenReport, RoadIssue } from "@/lib/types";
import { formatRelative, titleCase } from "@/lib/format";

const STATUS_META: Record<
  CitizenReport["status"],
  { label: string; variant: "warning" | "secondary" | "default" | "success" }
> = {
  new: { label: "New", variant: "warning" },
  matched: { label: "Matched to detection", variant: "secondary" },
  converted: { label: "Work order created", variant: "default" },
  closed: { label: "Closed", variant: "success" },
};

export default function CitizenReportsPage() {
  const reduceMotion = useReducedMotion();
  const reportsQuery = useAsync(() => getCitizenReports(), []);
  const [reports, setReports] = React.useState<CitizenReport[]>([]);
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [matching, setMatching] = React.useState<CitizenReport | null>(null);

  React.useEffect(() => {
    if (reportsQuery.data) setReports(reportsQuery.data);
  }, [reportsQuery.data]);

  const visible =
    statusFilter === "all"
      ? reports
      : reports.filter((r) => r.status === statusFilter);

  const counts = {
    new: reports.filter((r) => r.status === "new").length,
    matched: reports.filter((r) => r.status === "matched" || r.status === "converted").length,
  };

  const updateReport = (updated: CitizenReport) =>
    setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));

  const convert = async (report: CitizenReport) => {
    const order = await createWorkOrder({
      title: `${report.category} — ${report.locationText}`,
      issueIds: report.matchedIssueId ? [report.matchedIssueId] : [],
      district: report.district,
    });
    const updated = await setCitizenReportStatus(report.id, "converted");
    updateReport(updated);
    toast.success(`${order.id} created from ${report.id}`, {
      description: "The resident can be notified when work is scheduled.",
    });
  };

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Citizen reports"
        description="311 and portal reports, cross-checked against AI detections so crews aren't dispatched twice. Mock data."
        actions={
          <Tabs value={statusFilter} onValueChange={setStatusFilter}>
            <TabsList aria-label="Filter by status" className="h-auto flex-wrap">
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="new">New ({counts.new})</TabsTrigger>
              <TabsTrigger value="matched">Matched</TabsTrigger>
              <TabsTrigger value="converted">Converted</TabsTrigger>
              <TabsTrigger value="closed">Closed</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      {/* Intake stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile icon={Inbox} label="Awaiting triage" value={reportsQuery.loading ? null : String(counts.new)} />
        <StatTile
          icon={Link2}
          label="Linked to a detection"
          value={reportsQuery.loading ? null : String(counts.matched)}
        />
        <StatTile icon={Phone} label="Channels" value="311 · Web · App" />
        <StatTile icon={CheckCircle2} label="Duplicate dispatches avoided" value="This demo: 2" />
      </div>

      {reportsQuery.loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title="No reports in this state"
          description="New citizen reports will appear here as they arrive from 311 and the resident portal."
        />
      ) : (
        <AnimatePresence initial={false}>
          {visible.map((report) => (
            <motion.div
              key={report.id}
              layout={!reduceMotion}
              initial={reduceMotion ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0 }}
            >
              <Card className="mb-3">
                <CardContent className="flex flex-col gap-4 p-4 sm:flex-row">
                  <div className="relative aspect-[8/5] w-full shrink-0 overflow-hidden rounded-md border bg-muted sm:w-44">
                    {report.photoSeed ? (
                      <RoadImage
                        seed={report.photoSeed}
                        classCode={report.category === "Pothole" ? "D40" : "D20"}
                        label={`Illustrative placeholder for the resident's photo on ${report.id}`}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-muted-foreground">
                        <span className="flex flex-col items-center gap-1 text-xs">
                          <ImageOff className="h-5 w-5" aria-hidden /> No photo
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="tnum text-sm font-semibold">{report.id}</span>
                      <Badge variant="outline">{report.category}</Badge>
                      <Badge variant={STATUS_META[report.status].variant}>
                        {STATUS_META[report.status].label}
                      </Badge>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {report.channel} · {formatRelative(report.submittedAt)}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">“{report.description}”</p>
                    <p className="mt-1.5 flex items-center gap-1 text-xs text-muted-foreground">
                      <MapPin className="h-3 w-3" aria-hidden />
                      {report.locationText} · {districtById(report.district).name}
                    </p>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {report.status === "new" && (
                        <>
                          <Button size="sm" onClick={() => setMatching(report)}>
                            <Link2 aria-hidden /> Match to detection
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => convert(report)}>
                            <ClipboardPlus aria-hidden /> Create work order
                          </Button>
                        </>
                      )}
                      {report.status === "matched" && (
                        <>
                          {report.matchedIssueId && (
                            <Button size="sm" variant="outline" asChild>
                              <Link href={`/issues/${report.matchedIssueId}`}>
                                View {report.matchedIssueId} <ArrowUpRight aria-hidden />
                              </Link>
                            </Button>
                          )}
                          <Button size="sm" onClick={() => convert(report)}>
                            <ClipboardPlus aria-hidden /> Create work order
                          </Button>
                        </>
                      )}
                      {report.status === "converted" && report.matchedIssueId && (
                        <Button size="sm" variant="outline" asChild>
                          <Link href={`/issues/${report.matchedIssueId}`}>
                            Linked detection {report.matchedIssueId} <ArrowUpRight aria-hidden />
                          </Link>
                        </Button>
                      )}
                      {(report.status === "new" || report.status === "matched") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            updateReport(await setCitizenReportStatus(report.id, "closed"));
                            toast.success(`${report.id} closed`);
                          }}
                        >
                          Close
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </AnimatePresence>
      )}

      <MatchDialog
        report={matching}
        onClose={() => setMatching(null)}
        onMatched={updateReport}
      />
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string | null;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon className="h-3.5 w-3.5" aria-hidden />
          {label}
        </p>
        {value === null ? (
          <Skeleton className="mt-2 h-6 w-14" />
        ) : (
          <p className="tnum mt-1 text-lg font-semibold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

function MatchDialog({
  report,
  onClose,
  onMatched,
}: {
  report: CitizenReport | null;
  onClose: () => void;
  onMatched: (report: CitizenReport) => void;
}) {
  const [suggestions, setSuggestions] = React.useState<RoadIssue[] | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (report) {
      setSuggestions(null);
      suggestMatches(report.id).then(setSuggestions).catch(() => setSuggestions([]));
    }
  }, [report]);

  const link = async (issueId: string) => {
    if (!report) return;
    setBusy(issueId);
    try {
      const updated = await matchCitizenReport(report.id, issueId);
      onMatched(updated);
      onClose();
      toast.success(`${report.id} linked to ${issueId}`, {
        description: "The report and detection now share one repair record.",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={!!report} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Match {report?.id} to an AI detection</DialogTitle>
          <DialogDescription>
            Nearby open detections, closest first. Linking avoids a duplicate
            crew dispatch. Demo only.
          </DialogDescription>
        </DialogHeader>
        {suggestions === null ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : suggestions.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No open detections nearby. You can still create a work order directly.
          </p>
        ) : (
          <ul className="space-y-2">
            {suggestions.map((issue) => (
              <li
                key={issue.id}
                className="flex items-center gap-3 rounded-md border p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    <span className="tnum">{issue.id}</span> · {issue.roadName}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <ClassBadge code={issue.classCode} short />
                    <span className="text-xs text-muted-foreground">
                      {titleCase(issue.severity)} severity
                    </span>
                  </div>
                </div>
                <PriorityScore score={issue.priorityScore} />
                <Button size="sm" onClick={() => link(issue.id)} disabled={busy !== null}>
                  {busy === issue.id ? "Linking…" : "Link"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
