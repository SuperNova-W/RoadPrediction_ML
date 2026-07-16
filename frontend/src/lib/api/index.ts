/**
 * RoadLens mock service layer.
 *
 * Every UI screen talks to these functions instead of importing mock data
 * directly. Each function simulates network latency and returns typed
 * results, so swapping in a real backend (e.g. the Python inference API)
 * means re-implementing this module's function bodies with `fetch` calls —
 * the signatures and types stay the same. See src/lib/api/README.md.
 */
import { BRAND } from "@/lib/brand";
import {
  type ActivityEvent,
  type AppNotification,
  type AuditEntry,
  type DamageClassCode,
  type DashboardStats,
  type District,
  type FleetVehicle,
  type Integration,
  type IssueFilters,
  type MonthlyTrendPoint,
  type ReviewStatus,
  type RoadIssue,
  type TeamMember,
  type WorkOrder,
  type WorkOrderStatus,
} from "@/lib/types";
import type {
  PeerBenchmark,
  PerformanceMeasure,
  CitizenReport,
  CitizenReportStatus,
  ExecutiveSummary,
  RoadSegment,
} from "@/lib/types";
import { ACTIVITY, AUDIT_LOG, INTEGRATIONS, NOTIFICATIONS, TEAM } from "@/lib/mock/misc";
import { PEER_BENCHMARK, PERFORMANCE_MEASURES } from "@/lib/mock/analytics";
import {
  CITIZEN_REPORTS,
  EXECUTIVE_SUMMARY,
  ROAD_SEGMENTS,
} from "@/lib/mock/government";
import { DISTRICTS } from "@/lib/mock/districts";
import { ISSUES } from "@/lib/mock/issues";
import { DISTRICT_REPORT, MONTHLY_TRENDS, type DistrictReportRow } from "@/lib/mock/trends";
import { VEHICLES } from "@/lib/mock/vehicles";
import { WORK_ORDERS } from "@/lib/mock/work-orders";

/** Simulated latency keeps loading states honest without feeling slow. */
function delay(ms = 350): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms + Math.random() * 150));
}

/* ------------------------------------------------------------------ */
/* In-memory demo store (mutations persist for the browser session).   */
/* ------------------------------------------------------------------ */

const store = {
  issues: ISSUES.map((i) => ({ ...i })),
  workOrders: WORK_ORDERS.map((w) => ({ ...w })),
  activity: [...ACTIVITY],
  notifications: NOTIFICATIONS.map((n) => ({ ...n })),
};

let workOrderCounter = 238;

/* ------------------------------------------------------------------ */
/* Issues                                                              */
/* ------------------------------------------------------------------ */

export async function getIssues(filters: IssueFilters = {}): Promise<RoadIssue[]> {
  await delay();
  let rows = [...store.issues];

  if (filters.search) {
    const q = filters.search.toLowerCase();
    rows = rows.filter(
      (i) =>
        i.id.toLowerCase().includes(q) ||
        i.roadName.toLowerCase().includes(q) ||
        i.district.toLowerCase().includes(q),
    );
  }
  if (filters.classCodes?.length)
    rows = rows.filter((i) => filters.classCodes!.includes(i.classCode));
  if (filters.severities?.length)
    rows = rows.filter((i) => filters.severities!.includes(i.severity));
  if (filters.reviewStatuses?.length)
    rows = rows.filter((i) => filters.reviewStatuses!.includes(i.reviewStatus));
  if (filters.districts?.length)
    rows = rows.filter((i) => filters.districts!.includes(i.district));
  if (filters.minConfidence !== undefined)
    rows = rows.filter((i) => i.confidence >= filters.minConfidence!);
  if (filters.minPriority !== undefined)
    rows = rows.filter((i) => i.priorityScore >= filters.minPriority!);
  if (filters.capturedAfter)
    rows = rows.filter((i) => i.capturedAt >= filters.capturedAfter!);
  if (filters.capturedBefore)
    rows = rows.filter((i) => i.capturedAt <= filters.capturedBefore!);

  const sort = filters.sort ?? "priority";
  const dir = filters.sortDir === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    if (sort === "priority") return (a.priorityScore - b.priorityScore) * dir;
    if (sort === "confidence") return (a.confidence - b.confidence) * dir;
    return a.capturedAt.localeCompare(b.capturedAt) * dir;
  });

  return rows;
}

export async function getIssue(id: string): Promise<RoadIssue | null> {
  await delay(250);
  return store.issues.find((i) => i.id === id) ?? null;
}

export async function setIssueReview(
  id: string,
  status: ReviewStatus,
  reviewer = "You",
): Promise<RoadIssue> {
  await delay(400);
  const issue = store.issues.find((i) => i.id === id);
  if (!issue) throw new Error(`Issue ${id} not found`);
  issue.reviewStatus = status;
  if (status === "confirmed") issue.assignee = issue.assignee ?? reviewer;
  store.activity.unshift({
    id: `act-${Date.now()}`,
    issueId: id,
    type: status === "confirmed" ? "confirmed" : "rejected",
    actor: reviewer,
    actorIsSystem: false,
    message: `${status === "confirmed" ? "Confirmed" : "Rejected"} detection ${id}`,
    timestamp: new Date().toISOString(),
  });
  return { ...issue };
}

export async function getIssueActivity(issueId: string): Promise<ActivityEvent[]> {
  await delay(200);
  return store.activity.filter((a) => a.issueId === issueId);
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export async function getDashboardStats(): Promise<DashboardStats> {
  await delay();
  const open = store.issues.filter((i) => i.reviewStatus !== "rejected");
  const urgent = open.filter((i) => i.severity === "severe" || i.priorityScore >= 80);
  return {
    coveragePct: 0.68,
    coverageDeltaPct: 0.04,
    openIssues: 243, // network-wide demo total; the issue list shows a sample
    urgentIssues: 18 + urgent.length,
    milesAnalyzed: 1284,
    backlogEstimate: open.reduce((sum, i) => sum + i.estRepairCost, 0) + 512000,
  };
}

export async function getRecentActivity(): Promise<ActivityEvent[]> {
  await delay(250);
  return store.activity.slice(0, 8);
}

export async function getTrends(): Promise<MonthlyTrendPoint[]> {
  await delay();
  return MONTHLY_TRENDS;
}

export async function getDistrictReport(): Promise<DistrictReportRow[]> {
  await delay();
  return DISTRICT_REPORT;
}

/* ------------------------------------------------------------------ */
/* Reference data                                                      */
/* ------------------------------------------------------------------ */

export async function getDistricts(): Promise<District[]> {
  await delay(150);
  return DISTRICTS;
}

export async function getVehicles(): Promise<FleetVehicle[]> {
  await delay(250);
  return VEHICLES;
}

/* ------------------------------------------------------------------ */
/* Work orders                                                         */
/* ------------------------------------------------------------------ */

export async function getWorkOrders(): Promise<WorkOrder[]> {
  await delay();
  return store.workOrders.map((w) => ({ ...w }));
}

export async function setWorkOrderStatus(
  id: string,
  status: WorkOrderStatus,
): Promise<WorkOrder> {
  await delay(300);
  const order = store.workOrders.find((w) => w.id === id);
  if (!order) throw new Error(`Work order ${id} not found`);
  order.status = status;
  return { ...order };
}

export async function createWorkOrder(input: {
  title: string;
  issueIds: string[];
  district: string;
  crew?: string;
  costEstimate?: number;
}): Promise<WorkOrder> {
  await delay(450);
  const issues = store.issues.filter((i) => input.issueIds.includes(i.id));
  const order: WorkOrder = {
    id: `WO-${workOrderCounter++}`,
    title: input.title,
    issueIds: input.issueIds,
    status: "planned",
    crew: input.crew ?? "Unassigned",
    costEstimate:
      input.costEstimate ?? issues.reduce((s, i) => s + i.estRepairCost, 0),
    dueDate: new Date(Date.now() + 21 * 86400_000).toISOString(),
    createdAt: new Date().toISOString(),
    district: input.district,
    priority: issues.some((i) => i.severity === "severe")
      ? "severe"
      : issues.some((i) => i.severity === "high")
        ? "high"
        : "moderate",
  };
  store.workOrders.unshift(order);
  for (const issue of issues) issue.workOrderId = order.id;
  store.activity.unshift({
    id: `act-${Date.now()}`,
    issueId: input.issueIds[0] ?? null,
    type: "work_order",
    actor: "You",
    actorIsSystem: false,
    message: `Created ${order.id} (${order.title})`,
    timestamp: new Date().toISOString(),
  });
  return { ...order };
}

/* ------------------------------------------------------------------ */
/* Misc                                                                */
/* ------------------------------------------------------------------ */

export async function getIntegrations(): Promise<Integration[]> {
  await delay();
  return INTEGRATIONS;
}

export async function getTeam(): Promise<TeamMember[]> {
  await delay();
  return TEAM;
}

export async function getAuditLog(): Promise<AuditEntry[]> {
  await delay();
  return AUDIT_LOG;
}

export async function getNotifications(): Promise<AppNotification[]> {
  await delay(200);
  return store.notifications;
}

export async function markNotificationsRead(): Promise<void> {
  await delay(100);
  store.notifications = store.notifications.map((n) => ({ ...n, read: true }));
}

/** Simulated mock detection for the ingestion demo — NOT a model call. */
export function mockDetectionsForUpload(seed: number) {
  const classes: DamageClassCode[] = ["D00", "D10", "D20", "D40"];
  const primary = classes[seed % classes.length];
  const jitter = (n: number) => ((seed * 9301 + n * 49297) % 233280) / 233280;
  return [
    {
      id: `up-${seed}-1`,
      classCode: primary,
      confidence: Math.round((0.68 + jitter(1) * 0.28) * 100) / 100,
      box: {
        x: 0.22 + jitter(2) * 0.3,
        y: 0.5 + jitter(3) * 0.15,
        width: 0.22 + jitter(4) * 0.2,
        height: 0.16 + jitter(5) * 0.18,
      },
    },
  ];
}

export const API_INFO = {
  product: BRAND.name,
  mode: "mock",
} as const;

/* ------------------------------------------------------------------ */
/* Government-facing views                                             */
/* ------------------------------------------------------------------ */

const govStore = {
  citizenReports: CITIZEN_REPORTS.map((r) => ({ ...r })),
};

export async function getRoadSegments(): Promise<RoadSegment[]> {
  await delay();
  return ROAD_SEGMENTS.map((s) => ({ ...s }));
}

export async function getExecutiveSummary(): Promise<ExecutiveSummary> {
  await delay();
  return EXECUTIVE_SUMMARY;
}

export async function getCitizenReports(): Promise<CitizenReport[]> {
  await delay();
  return govStore.citizenReports.map((r) => ({ ...r }));
}

/** Link a citizen report to an AI detection (demo, in-memory). */
export async function matchCitizenReport(
  reportId: string,
  issueId: string,
): Promise<CitizenReport> {
  await delay(350);
  const report = govStore.citizenReports.find((r) => r.id === reportId);
  if (!report) throw new Error(`Report ${reportId} not found`);
  report.status = "matched";
  report.matchedIssueId = issueId;
  return { ...report };
}

export async function setCitizenReportStatus(
  reportId: string,
  status: CitizenReportStatus,
): Promise<CitizenReport> {
  await delay(300);
  const report = govStore.citizenReports.find((r) => r.id === reportId);
  if (!report) throw new Error(`Report ${reportId} not found`);
  report.status = status;
  return { ...report };
}

/** Nearest open detections to a report, for the match-suggestion UI. */
export async function suggestMatches(reportId: string): Promise<RoadIssue[]> {
  await delay(250);
  const report = govStore.citizenReports.find((r) => r.id === reportId);
  if (!report) return [];
  const dist = (a: [number, number], b: [number, number]) =>
    Math.hypot(a[0] - b[0], a[1] - b[1]);
  return store.issues
    .filter((i) => i.reviewStatus !== "rejected")
    .sort(
      (a, b) =>
        dist(a.coordinates, report.coordinates) -
        dist(b.coordinates, report.coordinates),
    )
    .slice(0, 3);
}

/* ------------------------------------------------------------------ */
/* Performance analytics                                               */
/* ------------------------------------------------------------------ */

export async function getPerformanceMeasures(): Promise<PerformanceMeasure[]> {
  await delay();
  return PERFORMANCE_MEASURES;
}

export async function getPeerBenchmark(): Promise<PeerBenchmark> {
  await delay(300);
  return PEER_BENCHMARK;
}
