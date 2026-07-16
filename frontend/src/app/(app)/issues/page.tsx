"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowDownWideNarrow,
  ArrowUpRight,
  ChevronDown,
  ClipboardPlus,
  ListFilter,
  MapIcon,
  SearchX,
  Table2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { ClassBadge, PriorityScore, ReviewBadge, SeverityBadge } from "@/components/domain/badges";
import { DetectionOverlay } from "@/components/domain/detection-overlay";
import { RoadImage } from "@/components/domain/road-image";
import { IssueMap } from "@/components/map/issue-map";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createWorkOrder, getDistricts, getIssues } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { MOCK_NOW } from "@/lib/mock/seed";
import {
  DAMAGE_CLASSES,
  SEVERITY_ORDER,
  type DamageClassCode,
  type ReviewStatus,
  type RoadIssue,
  type Severity,
} from "@/lib/types";
import { formatConfidence, formatDateTime, titleCase } from "@/lib/format";

const CLASS_CODES = Object.keys(DAMAGE_CLASSES) as DamageClassCode[];
const REVIEW_STATUSES: ReviewStatus[] = ["pending", "confirmed", "rejected"];

interface Chip {
  key: string;
  label: string;
  onRemove: () => void;
}

export default function IssuesPage() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();

  const [view, setView] = React.useState<"table" | "map">("table");
  const [search, setSearch] = React.useState("");
  const [classCodes, setClassCodes] = React.useState<DamageClassCode[]>([]);
  const [severities, setSeverities] = React.useState<Severity[]>([]);
  const [statuses, setStatuses] = React.useState<ReviewStatus[]>([]);
  const [districtIds, setDistrictIds] = React.useState<string[]>([]);
  const [minConfidence, setMinConfidence] = React.useState(0);
  const [minPriority, setMinPriority] = React.useState(0);
  const [dateRange, setDateRange] = React.useState("all");
  const [sortDir, setSortDir] = React.useState<"desc" | "asc">("desc");
  const [expanded, setExpanded] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [creating, setCreating] = React.useState(false);

  const capturedAfter =
    dateRange === "all"
      ? undefined
      : new Date(MOCK_NOW - Number(dateRange) * 86400_000).toISOString();

  const districts = useAsync(() => getDistricts(), []);
  const issues = useAsync(
    () =>
      getIssues({
        search,
        classCodes: classCodes.length ? classCodes : undefined,
        severities: severities.length ? severities : undefined,
        reviewStatuses: statuses.length ? statuses : undefined,
        districts: districtIds.length ? districtIds : undefined,
        minConfidence: minConfidence > 0 ? minConfidence / 100 : undefined,
        minPriority: minPriority > 0 ? minPriority : undefined,
        capturedAfter,
        sort: "priority",
        sortDir,
      }),
    [search, classCodes, severities, statuses, districtIds, minConfidence, minPriority, capturedAfter, sortDir],
  );

  const rows = issues.data ?? [];
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  const toggle = <T,>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const chips: Chip[] = [
    ...classCodes.map((c) => ({
      key: `c-${c}`,
      label: DAMAGE_CLASSES[c].short,
      onRemove: () => setClassCodes((l) => l.filter((x) => x !== c)),
    })),
    ...severities.map((s) => ({
      key: `s-${s}`,
      label: titleCase(s),
      onRemove: () => setSeverities((l) => l.filter((x) => x !== s)),
    })),
    ...statuses.map((s) => ({
      key: `r-${s}`,
      label: titleCase(s),
      onRemove: () => setStatuses((l) => l.filter((x) => x !== s)),
    })),
    ...districtIds.map((d) => ({
      key: `d-${d}`,
      label: districts.data?.find((x) => x.id === d)?.name ?? d,
      onRemove: () => setDistrictIds((l) => l.filter((x) => x !== d)),
    })),
    ...(minConfidence > 0
      ? [{ key: "conf", label: `Confidence ≥ ${minConfidence}%`, onRemove: () => setMinConfidence(0) }]
      : []),
    ...(minPriority > 0
      ? [{ key: "prio", label: `Priority ≥ ${minPriority}`, onRemove: () => setMinPriority(0) }]
      : []),
    ...(dateRange !== "all"
      ? [{ key: "date", label: `Last ${dateRange} days`, onRemove: () => setDateRange("all") }]
      : []),
  ];

  const bulkCreateWorkOrder = async () => {
    const ids = [...selected];
    if (ids.length === 0) return;
    setCreating(true);
    try {
      const first = rows.find((r) => r.id === ids[0]);
      const order = await createWorkOrder({
        title: `Batch repair — ${ids.length} detections`,
        issueIds: ids,
        district: first?.district ?? "riverside",
      });
      toast.success(`${order.id} created`, {
        description: `${ids.length} detections linked. View it in Work orders.`,
        action: { label: "Open", onClick: () => router.push("/work-orders") },
      });
      setSelected(new Set());
      issues.reload();
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Issues"
        description="AI-detected road damage awaiting review and repair. Mock data."
        actions={
          <Tabs value={view} onValueChange={(v) => setView(v as "table" | "map")}>
            <TabsList aria-label="Switch view">
              <TabsTrigger value="table">
                <Table2 aria-hidden /> Table
              </TabsTrigger>
              <TabsTrigger value="map">
                <MapIcon aria-hidden /> Map
              </TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by ID, road, district…"
          className="w-full sm:w-64"
          aria-label="Search issues"
        />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <ListFilter aria-hidden /> Damage type
              {classCodes.length > 0 && <Badge variant="secondary">{classCodes.length}</Badge>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Damage type</DropdownMenuLabel>
            {CLASS_CODES.map((code) => (
              <DropdownMenuCheckboxItem
                key={code}
                checked={classCodes.includes(code)}
                onCheckedChange={() => setClassCodes((l) => toggle(l, code))}
                onSelect={(e) => e.preventDefault()}
              >
                {DAMAGE_CLASSES[code].label}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              Severity
              {severities.length > 0 && <Badge variant="secondary">{severities.length}</Badge>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Estimated severity</DropdownMenuLabel>
            {SEVERITY_ORDER.map((s) => (
              <DropdownMenuCheckboxItem
                key={s}
                checked={severities.includes(s)}
                onCheckedChange={() => setSeverities((l) => toggle(l, s))}
                onSelect={(e) => e.preventDefault()}
              >
                {titleCase(s)}
              </DropdownMenuCheckboxItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Review status</DropdownMenuLabel>
            {REVIEW_STATUSES.map((s) => (
              <DropdownMenuCheckboxItem
                key={s}
                checked={statuses.includes(s)}
                onCheckedChange={() => setStatuses((l) => toggle(l, s))}
                onSelect={(e) => e.preventDefault()}
              >
                {titleCase(s)}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              District
              {districtIds.length > 0 && <Badge variant="secondary">{districtIds.length}</Badge>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>District</DropdownMenuLabel>
            {(districts.data ?? []).map((d) => (
              <DropdownMenuCheckboxItem
                key={d.id}
                checked={districtIds.includes(d.id)}
                onCheckedChange={() => setDistrictIds((l) => toggle(l, d.id))}
                onSelect={(e) => e.preventDefault()}
              >
                {d.name}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm">
              Thresholds <ChevronDown aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72 space-y-5" align="start">
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="conf-slider">Min. confidence</Label>
                <span className="tnum text-sm text-muted-foreground">{minConfidence}%</span>
              </div>
              <Slider
                id="conf-slider"
                value={[minConfidence]}
                onValueChange={([v]) => setMinConfidence(v)}
                max={95}
                step={5}
                aria-label="Minimum confidence"
              />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="prio-slider">Min. priority score</Label>
                <span className="tnum text-sm text-muted-foreground">{minPriority}</span>
              </div>
              <Slider
                id="prio-slider"
                value={[minPriority]}
                onValueChange={([v]) => setMinPriority(v)}
                max={95}
                step={5}
                aria-label="Minimum priority score"
              />
            </div>
          </PopoverContent>
        </Popover>

        <Select value={dateRange} onValueChange={setDateRange}>
          <SelectTrigger className="h-8 w-36 text-sm" aria-label="Capture date range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any date</SelectItem>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
          aria-label={`Sort by priority ${sortDir === "desc" ? "descending" : "ascending"}`}
        >
          <ArrowDownWideNarrow aria-hidden className={sortDir === "asc" ? "rotate-180" : ""} />
          Priority
        </Button>
      </div>

      {/* Active filter chips */}
      <AnimatePresence initial={false}>
        {chips.length > 0 && (
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
            className="flex flex-wrap items-center gap-1.5 overflow-hidden"
          >
            {chips.map((chip) => (
              <motion.span key={chip.key} layout={!reduceMotion}>
                <Badge variant="secondary" className="gap-1 pr-1">
                  {chip.label}
                  <button
                    onClick={chip.onRemove}
                    className="rounded-full p-0.5 hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label={`Remove filter ${chip.label}`}
                  >
                    <X className="h-3 w-3" aria-hidden />
                  </button>
                </Badge>
              </motion.span>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bulk action bar */}
      <AnimatePresence>
        {selected.size > 0 && (
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: -8 }}
            className="flex items-center gap-3 rounded-md border bg-accent px-4 py-2"
          >
            <p className="text-sm font-medium">
              {selected.size} selected
            </p>
            <Button size="sm" onClick={bulkCreateWorkOrder} disabled={creating}>
              <ClipboardPlus aria-hidden />
              {creating ? "Creating…" : "Create work order"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {view === "map" ? (
        <Card>
          <CardContent className="h-[560px] p-2">
            {issues.loading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <IssueMap
                issues={rows}
                districts={districts.data ?? []}
                showDistricts
                onSelect={(id) => id && router.push(`/issues/${id}`)}
              />
            )}
          </CardContent>
        </Card>
      ) : issues.loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No issues match these filters"
          description="Try broadening the damage type, severity, or date filters."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearch("");
                setClassCodes([]);
                setSeverities([]);
                setStatuses([]);
                setDistrictIds([]);
                setMinConfidence(0);
                setMinPriority(0);
                setDateRange("all");
              }}
            >
              Clear all filters
            </Button>
          }
        />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 pl-4">
                  <Checkbox
                    checked={allSelected ? true : selected.size > 0 ? "indeterminate" : false}
                    onCheckedChange={(checked) =>
                      setSelected(checked ? new Set(rows.map((r) => r.id)) : new Set())
                    }
                    aria-label="Select all rows"
                  />
                </TableHead>
                <TableHead>Issue</TableHead>
                <TableHead className="hidden md:table-cell">Damage type</TableHead>
                <TableHead className="hidden sm:table-cell">Severity</TableHead>
                <TableHead className="hidden lg:table-cell">Confidence</TableHead>
                <TableHead className="hidden lg:table-cell">Status</TableHead>
                <TableHead className="text-right">Priority</TableHead>
                <TableHead className="w-10" aria-label="Expand" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((issue) => (
                <IssueRow
                  key={issue.id}
                  issue={issue}
                  expanded={expanded === issue.id}
                  onToggleExpand={() =>
                    setExpanded((e) => (e === issue.id ? null : issue.id))
                  }
                  selected={selected.has(issue.id)}
                  onToggleSelect={() =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (next.has(issue.id)) next.delete(issue.id);
                      else next.add(issue.id);
                      return next;
                    })
                  }
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function IssueRow({
  issue,
  expanded,
  onToggleExpand,
  selected,
  onToggleSelect,
}: {
  issue: RoadIssue;
  expanded: boolean;
  onToggleExpand: () => void;
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <>
      <TableRow data-state={selected ? "selected" : undefined}>
        <TableCell className="pl-4">
          <Checkbox
            checked={selected}
            onCheckedChange={onToggleSelect}
            aria-label={`Select ${issue.id}`}
          />
        </TableCell>
        <TableCell>
          <Link
            href={`/issues/${issue.id}`}
            className="group block outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          >
            <p className="font-medium group-hover:text-primary">
              <span className="tnum">{issue.id}</span>
              <ArrowUpRight
                className="ml-1 inline h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100"
                aria-hidden
              />
            </p>
            <p className="text-xs text-muted-foreground">
              {issue.roadName} · {formatDateTime(issue.capturedAt)}
            </p>
          </Link>
        </TableCell>
        <TableCell className="hidden md:table-cell">
          <ClassBadge code={issue.classCode} short />
        </TableCell>
        <TableCell className="hidden sm:table-cell">
          <SeverityBadge severity={issue.severity} />
        </TableCell>
        <TableCell className="tnum hidden text-sm lg:table-cell">
          {formatConfidence(issue.confidence)}
        </TableCell>
        <TableCell className="hidden lg:table-cell">
          <ReviewBadge status={issue.reviewStatus} />
        </TableCell>
        <TableCell className="text-right">
          <PriorityScore score={issue.priorityScore} />
        </TableCell>
        <TableCell>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleExpand}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} preview for ${issue.id}`}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`}
              aria-hidden
            />
          </Button>
        </TableCell>
      </TableRow>
      <AnimatePresence initial={false}>
        {expanded && (
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={8} className="p-0">
              <motion.div
                initial={reduceMotion ? false : { height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <div className="flex flex-col gap-4 bg-muted/40 p-4 sm:flex-row">
                  <div className="relative aspect-[8/5] w-full max-w-xs shrink-0 overflow-hidden rounded-md border">
                    <RoadImage seed={issue.imageSeed} classCode={issue.classCode} />
                    <DetectionOverlay detections={issue.detections} showLabels={false} />
                  </div>
                  <div className="grid flex-1 grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                    <Meta label="District" value={titleCase(issue.district.replace("-", " "))} />
                    <Meta label="Source vehicle" value={issue.vehicleId} />
                    <Meta label="Assignee" value={issue.assignee ?? "Unassigned"} />
                    <Meta label="Est. repair cost" value={`$${issue.estRepairCost.toLocaleString()}`} />
                    <Meta label="Detections" value={`${issue.detections.length}`} />
                    <Meta
                      label="Work order"
                      value={issue.workOrderId ?? "None"}
                    />
                    <div className="col-span-2 mt-1 sm:col-span-3">
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/issues/${issue.id}`}>
                          Open issue <ArrowUpRight aria-hidden />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </div>
              </motion.div>
            </TableCell>
          </TableRow>
        )}
      </AnimatePresence>
    </>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}
