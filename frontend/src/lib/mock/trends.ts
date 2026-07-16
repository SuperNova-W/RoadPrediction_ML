import type { MonthlyTrendPoint } from "@/lib/types";

/** Twelve months of clearly fictional trend data for charts. */
export const MONTHLY_TRENDS: MonthlyTrendPoint[] = [
  { month: "2025-08", label: "Aug", detections: 118, resolved: 74, avgPriority: 48, byClass: { D00: 41, D10: 22, D20: 31, D40: 24 }, completionRate: 0.58 },
  { month: "2025-09", label: "Sep", detections: 132, resolved: 89, avgPriority: 50, byClass: { D00: 44, D10: 25, D20: 35, D40: 28 }, completionRate: 0.61 },
  { month: "2025-10", label: "Oct", detections: 141, resolved: 96, avgPriority: 51, byClass: { D00: 46, D10: 26, D20: 38, D40: 31 }, completionRate: 0.63 },
  { month: "2025-11", label: "Nov", detections: 126, resolved: 88, avgPriority: 53, byClass: { D00: 40, D10: 24, D20: 34, D40: 28 }, completionRate: 0.64 },
  { month: "2025-12", label: "Dec", detections: 98, resolved: 71, avgPriority: 55, byClass: { D00: 30, D10: 18, D20: 27, D40: 23 }, completionRate: 0.62 },
  { month: "2026-01", label: "Jan", detections: 155, resolved: 82, avgPriority: 61, byClass: { D00: 47, D10: 28, D20: 41, D40: 39 }, completionRate: 0.55 },
  { month: "2026-02", label: "Feb", detections: 189, resolved: 90, avgPriority: 66, byClass: { D00: 55, D10: 33, D20: 51, D40: 50 }, completionRate: 0.52 },
  { month: "2026-03", label: "Mar", detections: 204, resolved: 121, avgPriority: 64, byClass: { D00: 60, D10: 36, D20: 55, D40: 53 }, completionRate: 0.56 },
  { month: "2026-04", label: "Apr", detections: 176, resolved: 138, avgPriority: 60, byClass: { D00: 54, D10: 32, D20: 48, D40: 42 }, completionRate: 0.63 },
  { month: "2026-05", label: "May", detections: 158, resolved: 129, avgPriority: 56, byClass: { D00: 50, D10: 30, D20: 43, D40: 35 }, completionRate: 0.67 },
  { month: "2026-06", label: "Jun", detections: 149, resolved: 127, avgPriority: 53, byClass: { D00: 49, D10: 28, D20: 40, D40: 32 }, completionRate: 0.71 },
  { month: "2026-07", label: "Jul", detections: 84, resolved: 66, avgPriority: 52, byClass: { D00: 27, D10: 16, D20: 23, D40: 18 }, completionRate: 0.72 },
];

export interface DistrictReportRow {
  district: string;
  open: number;
  resolved90d: number;
  avgPriority: number;
  backlogCost: number;
}

export const DISTRICT_REPORT: DistrictReportRow[] = [
  { district: "riverside", open: 64, resolved90d: 51, avgPriority: 58, backlogCost: 182000 },
  { district: "north-end", open: 47, resolved90d: 62, avgPriority: 49, backlogCost: 121000 },
  { district: "capitol", open: 22, resolved90d: 34, avgPriority: 41, backlogCost: 58000 },
  { district: "eastmoor", open: 71, resolved90d: 44, avgPriority: 63, backlogCost: 214000 },
  { district: "south-yards", open: 39, resolved90d: 29, avgPriority: 55, backlogCost: 97000 },
];
