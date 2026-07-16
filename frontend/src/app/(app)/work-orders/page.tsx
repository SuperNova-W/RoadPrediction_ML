"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CalendarDays,
  ClipboardList,
  ClipboardPlus,
  Columns3,
  HardHat,
  Link2,
  MoreHorizontal,
  Table2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { SeverityBadge, WorkOrderBadge } from "@/components/domain/badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createWorkOrder, getIssues, getWorkOrders, setWorkOrderStatus } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { districtById, DISTRICTS } from "@/lib/mock/districts";
import {
  WORK_ORDER_STATUSES,
  type RoadIssue,
  type WorkOrder,
  type WorkOrderStatus,
} from "@/lib/types";
import { formatCurrency, formatDate, titleCase } from "@/lib/format";

const COLUMN_LABELS: Record<WorkOrderStatus, string> = {
  planned: "Planned",
  approved: "Approved",
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
};

const CREWS = [
  "Crew A — Asphalt",
  "Crew B — Patching",
  "Crew C — Concrete",
  "Northside Paving Co. (contract)",
  "Halloway Rd. Services (contract)",
];

export default function WorkOrdersPage() {
  return (
    <React.Suspense fallback={null}>
      <WorkOrdersContent />
    </React.Suspense>
  );
}

function WorkOrdersContent() {
  const searchParams = useSearchParams();
  const [view, setView] = React.useState<"board" | "table">("board");
  const [orders, setOrders] = React.useState<WorkOrder[]>([]);
  const ordersQuery = useAsync(() => getWorkOrders(), []);
  const confirmedIssues = useAsync(
    () => getIssues({ reviewStatuses: ["confirmed"] }),
    [],
  );
  const [createOpen, setCreateOpen] = React.useState(
    searchParams.get("new") === "1",
  );

  React.useEffect(() => {
    if (ordersQuery.data) setOrders(ordersQuery.data);
  }, [ordersQuery.data]);

  const move = async (id: string, status: WorkOrderStatus) => {
    setOrders((prev) => prev.map((o) => (o.id === id ? { ...o, status } : o)));
    await setWorkOrderStatus(id, status);
    toast.success(`${id} moved to ${COLUMN_LABELS[status]}`);
  };

  const assign = async (id: string, crew: string) => {
    setOrders((prev) => prev.map((o) => (o.id === id ? { ...o, crew } : o)));
    toast.success(`${id} assigned to ${crew}`);
  };

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Work orders"
        description="Plan, schedule, and track repairs linked to confirmed detections."
        actions={
          <>
            <Tabs value={view} onValueChange={(v) => setView(v as "board" | "table")}>
              <TabsList aria-label="Switch view">
                <TabsTrigger value="board">
                  <Columns3 aria-hidden /> Board
                </TabsTrigger>
                <TabsTrigger value="table">
                  <Table2 aria-hidden /> Table
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <Button onClick={() => setCreateOpen(true)}>
              <ClipboardPlus aria-hidden /> New work order
            </Button>
          </>
        }
      />

      {ordersQuery.loading ? (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-full" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No work orders yet"
          description="Confirm detections in the Issues queue, then create work orders from them."
        />
      ) : view === "board" ? (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {WORK_ORDER_STATUSES.map((status) => {
            const items = orders.filter((o) => o.status === status);
            return (
              <section
                key={status}
                aria-label={`${COLUMN_LABELS[status]} column`}
                className="flex min-h-40 flex-col rounded-lg border bg-muted/40"
              >
                <header className="flex items-center justify-between px-3 py-2.5">
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {COLUMN_LABELS[status]}
                  </h2>
                  <span className="tnum rounded-full bg-secondary px-2 py-0.5 text-xs font-medium">
                    {items.length}
                  </span>
                </header>
                <div className="flex-1 space-y-2 px-2 pb-2">
                  <AnimatePresence initial={false}>
                    {items.map((order) => (
                      <BoardCard
                        key={order.id}
                        order={order}
                        onMove={move}
                        onAssign={assign}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Work order</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Crew</TableHead>
                <TableHead className="hidden sm:table-cell">District</TableHead>
                <TableHead className="hidden lg:table-cell">Detections</TableHead>
                <TableHead className="text-right">Cost est.</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Due</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="pl-4">
                    <p className="tnum font-medium">{order.id}</p>
                    <p className="max-w-64 truncate text-xs text-muted-foreground">
                      {order.title}
                    </p>
                  </TableCell>
                  <TableCell>
                    <WorkOrderBadge status={order.status} />
                  </TableCell>
                  <TableCell className="hidden text-sm md:table-cell">{order.crew}</TableCell>
                  <TableCell className="hidden text-sm sm:table-cell">
                    {districtById(order.district).name}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <span className="flex flex-wrap gap-1">
                      {order.issueIds.map((iid) => (
                        <Link
                          key={iid}
                          href={`/issues/${iid}`}
                          className="tnum inline-flex items-center gap-0.5 rounded bg-secondary px-1.5 py-0.5 text-xs font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Link2 className="h-3 w-3" aria-hidden />
                          {iid}
                        </Link>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="tnum text-right text-sm">
                    {formatCurrency(order.costEstimate)}
                  </TableCell>
                  <TableCell className="tnum hidden text-right text-sm sm:table-cell">
                    {formatDate(order.dueDate)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <CreateWorkOrderDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        issues={confirmedIssues.data ?? []}
        onCreated={(order) => setOrders((prev) => [order, ...prev])}
      />
    </div>
  );
}

function BoardCard({
  order,
  onMove,
  onAssign,
}: {
  order: WorkOrder;
  onMove: (id: string, status: WorkOrderStatus) => void;
  onAssign: (id: string, crew: string) => void;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.article
      layout={!reduceMotion}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={reduceMotion ? undefined : { opacity: 0, scale: 0.96 }}
      transition={{ type: "spring", stiffness: 500, damping: 40 }}
      className="rounded-md border bg-card p-3 shadow-card transition-shadow hover:shadow-raised"
      aria-label={`${order.id}: ${order.title}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="tnum text-xs font-semibold text-muted-foreground">{order.id}</p>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${order.id}`}>
              <MoreHorizontal className="h-4 w-4" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Move to</DropdownMenuLabel>
            {WORK_ORDER_STATUSES.filter((s) => s !== order.status).map((s) => (
              <DropdownMenuItem key={s} onSelect={() => onMove(order.id, s)}>
                {COLUMN_LABELS[s]}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Assign crew</DropdownMenuLabel>
            {CREWS.map((crew) => (
              <DropdownMenuItem key={crew} onSelect={() => onAssign(order.id, crew)}>
                {crew}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <p className="mt-1 text-sm font-medium leading-snug">{order.title}</p>
      <div className="mt-2 flex items-center gap-2">
        <SeverityBadge severity={order.priority} />
      </div>
      <div className="mt-2 space-y-1 text-xs text-muted-foreground">
        <p className="flex items-center gap-1.5">
          <HardHat className="h-3 w-3" aria-hidden /> {order.crew}
        </p>
        <p className="flex items-center gap-1.5">
          <CalendarDays className="h-3 w-3" aria-hidden />
          Due {formatDate(order.dueDate)} ·{" "}
          <span className="tnum">{formatCurrency(order.costEstimate)}</span>
        </p>
      </div>
      {order.issueIds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {order.issueIds.slice(0, 3).map((iid) => (
            <Link
              key={iid}
              href={`/issues/${iid}`}
              className="tnum rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {iid}
            </Link>
          ))}
          {order.issueIds.length > 3 && (
            <span className="text-[10px] text-muted-foreground">
              +{order.issueIds.length - 3} more
            </span>
          )}
        </div>
      )}
    </motion.article>
  );
}

function CreateWorkOrderDialog({
  open,
  onOpenChange,
  issues,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  issues: RoadIssue[];
  onCreated: (order: WorkOrder) => void;
}) {
  const [title, setTitle] = React.useState("");
  const [district, setDistrict] = React.useState(DISTRICTS[0].id);
  const [issueId, setIssueId] = React.useState<string>("none");
  const [crew, setCrew] = React.useState(CREWS[0]);
  const [busy, setBusy] = React.useState(false);

  const submit = async () => {
    if (!title.trim()) {
      toast.error("Give the work order a title");
      return;
    }
    setBusy(true);
    try {
      const order = await createWorkOrder({
        title: title.trim(),
        issueIds: issueId === "none" ? [] : [issueId],
        district,
        crew,
      });
      onCreated(order);
      onOpenChange(false);
      setTitle("");
      setIssueId("none");
      toast.success(`${order.id} created`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New work order</DialogTitle>
          <DialogDescription>
            Demo only — nothing is sent to an external system.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="new-wo-title">Title</Label>
            <Input
              id="new-wo-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Pothole repairs — Harlan Ave"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="new-wo-district">District</Label>
              <Select value={district} onValueChange={setDistrict}>
                <SelectTrigger id="new-wo-district">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DISTRICTS.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-wo-crew">Crew</Label>
              <Select value={crew} onValueChange={setCrew}>
                <SelectTrigger id="new-wo-crew">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CREWS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-wo-issue">Link a confirmed detection (optional)</Label>
            <Select value={issueId} onValueChange={setIssueId}>
              <SelectTrigger id="new-wo-issue">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No linked detection</SelectItem>
                {issues.map((issue) => (
                  <SelectItem key={issue.id} value={issue.id}>
                    {issue.id} · {issue.roadName} ({titleCase(issue.severity)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
