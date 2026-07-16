/**
 * Typed domain models shared by the mock service layer and the UI.
 * These mirror the shapes a future Python inference/backend API would
 * return; see src/lib/api/README.md for the replacement contract.
 */

export type DamageClassCode = "D00" | "D10" | "D20" | "D40";

export interface DamageClassInfo {
  code: DamageClassCode;
  label: string;
  short: string;
  description: string;
}

export const DAMAGE_CLASSES: Record<DamageClassCode, DamageClassInfo> = {
  D00: {
    code: "D00",
    label: "Longitudinal crack",
    short: "Longitudinal",
    description: "Crack running parallel to the direction of travel.",
  },
  D10: {
    code: "D10",
    label: "Transverse crack",
    short: "Transverse",
    description: "Crack running across the lane, perpendicular to travel.",
  },
  D20: {
    code: "D20",
    label: "Alligator crack",
    short: "Alligator",
    description: "Interconnected fatigue cracking resembling alligator skin.",
  },
  D40: {
    code: "D40",
    label: "Pothole",
    short: "Pothole",
    description: "Bowl-shaped depression with material loss from the surface.",
  },
};

export type Severity = "low" | "moderate" | "high" | "severe";
export const SEVERITY_ORDER: Severity[] = ["low", "moderate", "high", "severe"];

export type ReviewStatus = "pending" | "confirmed" | "rejected";

export type WorkOrderStatus =
  | "planned"
  | "approved"
  | "scheduled"
  | "in_progress"
  | "completed";

export const WORK_ORDER_STATUSES: WorkOrderStatus[] = [
  "planned",
  "approved",
  "scheduled",
  "in_progress",
  "completed",
];

/** Normalized [0..1] box relative to the source image. */
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Detection {
  id: string;
  classCode: DamageClassCode;
  confidence: number; // 0..1
  box: BoundingBox;
}

export interface RoadIssue {
  id: string; // e.g. "RL-1042"
  coordinates: [number, number]; // [lng, lat]
  roadName: string;
  district: string; // District id
  classCode: DamageClassCode;
  confidence: number; // primary detection confidence, 0..1
  severity: Severity; // heuristic estimate — not an engineering assessment
  priorityScore: number; // 0..100 composite repair priority
  reviewStatus: ReviewStatus;
  workOrderId: string | null;
  capturedAt: string; // ISO timestamp
  vehicleId: string;
  imageSeed: number; // drives the procedural placeholder image
  detections: Detection[];
  assignee: string | null;
  estRepairCost: number; // USD, rough planning estimate
}

export interface District {
  id: string;
  name: string;
  centroid: [number, number];
  /** Closed polygon ring, [lng, lat] pairs. */
  boundary: [number, number][];
  laneMiles: number;
}

export type VehicleStatus = "active" | "idle" | "offline";

export interface FleetVehicle {
  id: string;
  name: string;
  kind: string; // e.g. "Public works pickup"
  status: VehicleStatus;
  lastSeen: string; // ISO
  milesToday: number;
  imagesToday: number;
  district: string;
}

export interface WorkOrder {
  id: string; // e.g. "WO-231"
  title: string;
  issueIds: string[];
  status: WorkOrderStatus;
  crew: string;
  costEstimate: number;
  dueDate: string; // ISO date
  createdAt: string;
  district: string;
  priority: Severity;
}

export type ActivityType =
  | "detected"
  | "confirmed"
  | "rejected"
  | "assigned"
  | "work_order"
  | "note"
  | "status";

export interface ActivityEvent {
  id: string;
  issueId: string | null;
  type: ActivityType;
  actor: string; // "RoadLens detection" for AI events, otherwise a person
  actorIsSystem: boolean;
  message: string;
  timestamp: string;
}

export interface MonthlyTrendPoint {
  month: string; // "2026-01"
  label: string; // "Jan"
  detections: number;
  resolved: number;
  avgPriority: number;
  byClass: Record<DamageClassCode, number>;
  completionRate: number; // 0..1
}

export interface DashboardStats {
  coveragePct: number;
  coverageDeltaPct: number;
  openIssues: number;
  urgentIssues: number;
  milesAnalyzed: number;
  backlogEstimate: number; // USD
}

export type IntegrationStatus = "connected" | "available" | "attention";

export interface Integration {
  id: string;
  name: string;
  category:
    | "Fleet cameras"
    | "Dashcam providers"
    | "GIS"
    | "Asset management"
    | "Developer";
  description: string;
  status: IntegrationStatus;
  detail: string;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "Admin" | "Supervisor" | "Engineer" | "Inspector" | "Viewer";
  lastActive: string;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  target: string;
  timestamp: string;
  ip: string;
}

export interface AppNotification {
  id: string;
  title: string;
  body: string;
  timestamp: string;
  read: boolean;
  kind: "detection" | "work_order" | "system";
}

/** Filters accepted by the issues service. */
export interface IssueFilters {
  search?: string;
  classCodes?: DamageClassCode[];
  severities?: Severity[];
  reviewStatuses?: ReviewStatus[];
  districts?: string[];
  minConfidence?: number;
  minPriority?: number;
  capturedAfter?: string;
  capturedBefore?: string;
  sort?: "priority" | "captured" | "confidence";
  sortDir?: "asc" | "desc";
}

export type IngestionStage =
  | "uploading"
  | "validating"
  | "detecting"
  | "geolocating"
  | "ready";

export const INGESTION_STAGES: IngestionStage[] = [
  "uploading",
  "validating",
  "detecting",
  "geolocating",
  "ready",
];

export interface IngestionJob {
  id: string;
  fileName: string;
  fileSize: number;
  previewUrl: string | null; // object URL for user uploads
  stage: IngestionStage;
  progress: number; // 0..1 within current stage
  startedAt: string;
  /** Mock detections revealed at the "ready" stage. Simulated — not model output. */
  result: Detection[] | null;
  imageSeed: number;
}

/* ------------------------------------------------------------------ */
/* Government-facing views: network condition, executive brief, 311    */
/* ------------------------------------------------------------------ */

export type ConditionGrade = "A" | "B" | "C" | "D" | "F";
export type ConditionTrend = "improving" | "stable" | "declining";

export interface RoadSegment {
  id: string; // e.g. "SEG-104"
  streetName: string;
  district: string; // District id
  lengthMiles: number;
  /** 0-100 composite condition score (heuristic, not a certified PCI). */
  conditionScore: number;
  grade: ConditionGrade;
  openIssues: number;
  lastInspected: string; // ISO
  trend: ConditionTrend;
}

export type CitizenReportStatus = "new" | "matched" | "converted" | "closed";
export type CitizenReportChannel = "311 call" | "Web portal" | "Mobile app";

export interface CitizenReport {
  id: string; // e.g. "CR-118"
  description: string;
  category: string; // e.g. "Pothole", "Cracked pavement"
  locationText: string;
  coordinates: [number, number];
  district: string;
  submittedAt: string;
  channel: CitizenReportChannel;
  status: CitizenReportStatus;
  /** Linked AI detection, when a match has been confirmed. */
  matchedIssueId: string | null;
  photoSeed: number | null; // procedural placeholder photo, if attached
}

export interface BudgetSummary {
  fiscalYear: string; // "FY 2026"
  allocated: number;
  committed: number; // approved/scheduled work orders
  spent: number; // completed work
}

export interface ResponseMetric {
  severity: Severity;
  medianDaysToReview: number;
  medianDaysToRepair: number;
}

export interface ExecutiveSummary {
  conditionScore: number; // network average, 0-100
  conditionDelta: number; // vs prior quarter
  budget: BudgetSummary;
  response: ResponseMetric[];
  backlogTrend: { label: string; backlog: number }[]; // monthly est. $ backlog
  highlights: string[];
}
