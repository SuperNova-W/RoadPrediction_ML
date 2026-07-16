"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowLeft,
  Bot,
  Check,
  ClipboardPlus,
  Eye,
  EyeOff,
  FileQuestion,
  MapPin,
  UserCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { ClassBadge, PriorityScore, ReviewBadge } from "@/components/domain/badges";
import { DetectionOverlay } from "@/components/domain/detection-overlay";
import { RoadImage } from "@/components/domain/road-image";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  createWorkOrder,
  getIssue,
  getIssueActivity,
  setIssueReview,
} from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { DAMAGE_CLASSES, type ActivityEvent, type RoadIssue } from "@/lib/types";
import {
  formatConfidence,
  formatDateTime,
  formatRelative,
  titleCase,
} from "@/lib/format";
import { districtById } from "@/lib/mock/districts";
import { vehicleById } from "@/lib/mock/vehicles";
import { cn } from "@/lib/utils";

export function IssueDetail({ id }: { id: string }) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const issueQuery = useAsync(() => getIssue(id), [id]);
  const activityQuery = useAsync(() => getIssueActivity(id), [id]);
  const [issue, setIssue] = React.useState<RoadIssue | null>(null);
  const [showBoxes, setShowBoxes] = React.useState(true);
  const [reviewBusy, setReviewBusy] = React.useState(false);
  const [woOpen, setWoOpen] = React.useState(false);
  const [woTitle, setWoTitle] = React.useState("");
  const [woBusy, setWoBusy] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [localEvents, setLocalEvents] = React.useState<ActivityEvent[]>([]);

  React.useEffect(() => {
    if (issueQuery.data) {
      setIssue(issueQuery.data);
      setWoTitle(
        `${DAMAGE_CLASSES[issueQuery.data.classCode].short} repair — ${issueQuery.data.roadName}`,
      );
    }
  }, [issueQuery.data]);

  if (issueQuery.loading) {
    return (
      <div className="space-y-4 p-4 sm:p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-96 lg:col-span-2" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (!issue) {
    return (
      <div className="p-6">
        <EmptyState
          icon={FileQuestion}
          title={`Issue ${id} not found`}
          description="It may have been removed from the demo dataset."
          action={
            <Button variant="outline" asChild>
              <Link href="/issues">Back to issues</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const review = async (status: "confirmed" | "rejected") => {
    setReviewBusy(true);
    try {
      const updated = await setIssueReview(issue.id, status);
      setIssue(updated);
      toast.success(
        status === "confirmed" ? "Detection confirmed" : "Detection rejected",
        {
          description:
            status === "confirmed"
              ? "Marked as human-verified. It can now be added to a work order."
              : "Removed from the priority queue. This is recorded in the audit log.",
        },
      );
      activityQuery.reload();
    } finally {
      setReviewBusy(false);
    }
  };

  const submitWorkOrder = async () => {
    setWoBusy(true);
    try {
      const order = await createWorkOrder({
        title: woTitle || `Repair — ${issue.roadName}`,
        issueIds: [issue.id],
        district: issue.district,
      });
      setIssue({ ...issue, workOrderId: order.id });
      setWoOpen(false);
      toast.success(`${order.id} created`, {
        description: "Linked to this detection.",
        action: { label: "View", onClick: () => router.push("/work-orders") },
      });
    } finally {
      setWoBusy(false);
    }
  };

  const addNote = () => {
    if (!note.trim()) return;
    setLocalEvents((prev) => [
      {
        id: `local-${Date.now()}`,
        issueId: issue.id,
        type: "note",
        actor: "You",
        actorIsSystem: false,
        message: note.trim(),
        timestamp: new Date().toISOString(),
      },
      ...prev,
    ]);
    setNote("");
    toast.success("Note added");
  };

  const events = [...localEvents, ...(activityQuery.data ?? [])];
  const district = districtById(issue.district);
  const vehicle = vehicleById(issue.vehicleId);

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-4 p-4 sm:p-6"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild aria-label="Back to issues">
          <Link href="/issues">
            <ArrowLeft className="h-4 w-4" aria-hidden />
          </Link>
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">
            <span className="tnum">{issue.id}</span> · {issue.roadName}
          </h1>
          <p className="text-sm text-muted-foreground">
            {district.name} · captured {formatDateTime(issue.capturedAt)} by {vehicle.name}
          </p>
        </div>
        <ReviewBadge status={issue.reviewStatus} />
        <PriorityScore score={issue.priorityScore} className="text-base" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Image + detections */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-primary" aria-hidden />
                Source image · AI detections
              </CardTitle>
              <CardDescription>
                Illustrative placeholder frame. Bounding boxes are mock model
                output pending human review.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowBoxes((v) => !v)}
              aria-pressed={showBoxes}
            >
              {showBoxes ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
              {showBoxes ? "Hide boxes" : "Show boxes"}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="relative aspect-[8/5] w-full overflow-hidden rounded-lg border">
              <RoadImage seed={issue.imageSeed} classCode={issue.classCode} />
              <DetectionOverlay detections={issue.detections} visible={showBoxes} />
            </div>

            {/* Detection list */}
            <ul className="mt-4 space-y-2" aria-label="Detections">
              {issue.detections.map((det) => (
                <li
                  key={det.id}
                  className="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2"
                >
                  <ClassBadge code={det.classCode} />
                  <span className="tnum text-sm text-muted-foreground">
                    Confidence {formatConfidence(det.confidence)}
                  </span>
                  <Badge variant="muted" className="ml-auto">
                    <Bot aria-hidden /> AI output
                  </Badge>
                </li>
              ))}
            </ul>

            <Separator className="my-4" />

            {/* AI vs human panel */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border bg-muted/40 p-3">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <Bot className="h-3.5 w-3.5" aria-hidden /> AI assessment (unverified)
                </p>
                <div className="mt-2 space-y-1.5 text-sm">
                  <MetaRow label="Damage type" value={DAMAGE_CLASSES[issue.classCode].label} />
                  <MetaRow label="Confidence" value={formatConfidence(issue.confidence)} />
                  <MetaRow label="Est. severity" value={`${titleCase(issue.severity)} (heuristic estimate)`} />
                  <MetaRow label="Priority score" value={`${issue.priorityScore} / 100`} />
                </div>
              </div>
              <div
                className={cn(
                  "rounded-md border p-3",
                  issue.reviewStatus === "confirmed"
                    ? "border-success/30 bg-success/5"
                    : "bg-card",
                )}
              >
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <UserCheck className="h-3.5 w-3.5" aria-hidden /> Human review
                </p>
                <div className="mt-2 space-y-1.5 text-sm">
                  <MetaRow label="Status" value={titleCase(issue.reviewStatus)} />
                  <MetaRow label="Assignee" value={issue.assignee ?? "Unassigned"} />
                  <MetaRow label="Work order" value={issue.workOrderId ?? "None"} />
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Severity and priority are model estimates. Final repair decisions
                  require review and do not replace a licensed engineering assessment.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Right rail */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <Button
                variant="success"
                disabled={reviewBusy || issue.reviewStatus === "confirmed"}
                onClick={() => review("confirmed")}
              >
                <Check aria-hidden />
                {issue.reviewStatus === "confirmed" ? "Confirmed" : "Confirm detection"}
              </Button>
              <Button
                variant="outline"
                disabled={reviewBusy || issue.reviewStatus === "rejected"}
                onClick={() => review("rejected")}
              >
                <X aria-hidden /> Reject
              </Button>
              <Button
                variant="default"
                disabled={!!issue.workOrderId}
                onClick={() => setWoOpen(true)}
              >
                <ClipboardPlus aria-hidden />
                {issue.workOrderId ? `Linked to ${issue.workOrderId}` : "Create work order"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground" aria-hidden />
                Location
              </CardTitle>
              <CardDescription className="tnum">
                {issue.coordinates[1].toFixed(5)}, {issue.coordinates[0].toFixed(5)}
              </CardDescription>
            </CardHeader>
            <CardContent className="h-52 pb-5">
              <IssueMap
                issues={[issue]}
                center={issue.coordinates}
                zoom={17}
                cluster={false}
                selectedId={issue.id}
                basemap="satellite"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notes &amp; activity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Add a note for the crew…"
                  aria-label="New note"
                  className="min-h-[44px]"
                />
                <Button size="sm" onClick={addNote} disabled={!note.trim()}>
                  Add
                </Button>
              </div>
              <ol className="relative space-y-4 border-l pl-4" aria-label="Activity timeline">
                {events.length === 0 && !activityQuery.loading ? (
                  <p className="text-sm text-muted-foreground">No activity yet.</p>
                ) : null}
                {events.map((event) => (
                  <li key={event.id} className="relative">
                    <span
                      className={cn(
                        "absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-card",
                        event.actorIsSystem ? "bg-primary" : "bg-success",
                      )}
                      aria-hidden
                    />
                    <p className="text-sm leading-snug">{event.message}</p>
                    <p className="text-xs text-muted-foreground">
                      {event.actor}
                      {event.actorIsSystem ? " (system)" : ""} · {formatRelative(event.timestamp)}
                    </p>
                  </li>
                ))}
                <li className="relative">
                  <span
                    className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-primary ring-4 ring-card"
                    aria-hidden
                  />
                  <p className="text-sm leading-snug">
                    Detected by RoadLens from {vehicle.name} imagery
                  </p>
                  <p className="text-xs text-muted-foreground">
                    RoadLens detection (system) · {formatRelative(issue.capturedAt)}
                  </p>
                </li>
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Create work order dialog */}
      <Dialog open={woOpen} onOpenChange={setWoOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create work order</DialogTitle>
            <DialogDescription>
              Creates a planned work order linked to {issue.id}. Demo only — no
              external system is contacted.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="wo-title">Title</Label>
              <Input
                id="wo-title"
                value={woTitle}
                onChange={(e) => setWoTitle(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <MetaRow label="District" value={district.name} />
              <MetaRow label="Est. cost" value={`$${issue.estRepairCost.toLocaleString()}`} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWoOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitWorkOrder} disabled={woBusy}>
              {woBusy ? "Creating…" : "Create work order"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
