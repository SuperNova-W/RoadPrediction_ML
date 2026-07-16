import type {
  ActivityEvent,
  AppNotification,
  AuditEntry,
  Integration,
  TeamMember,
} from "@/lib/types";
import { hoursAgo, daysAgo } from "./seed";

export const ACTIVITY: ActivityEvent[] = [
  { id: "act-1", issueId: "RL-1001", type: "detected", actor: "RoadLens detection", actorIsSystem: true, message: "New severe pothole detected on Riverbend Pkwy", timestamp: hoursAgo(1.2) },
  { id: "act-2", issueId: "RL-1004", type: "confirmed", actor: "M. Okafor", actorIsSystem: false, message: "Confirmed alligator cracking after field photo review", timestamp: hoursAgo(2.6) },
  { id: "act-3", issueId: null, type: "work_order", actor: "J. Reyes", actorIsSystem: false, message: "Created WO-234 (Pothole + base repair — S Canal St)", timestamp: hoursAgo(4.1) },
  { id: "act-4", issueId: "RL-1009", type: "assigned", actor: "T. Lindqvist", actorIsSystem: false, message: "Assigned RL-1009 to A. Whitfield for review", timestamp: hoursAgo(6.8) },
  { id: "act-5", issueId: "RL-1017", type: "rejected", actor: "A. Whitfield", actorIsSystem: false, message: "Rejected detection — shadow misread as transverse crack", timestamp: hoursAgo(9.5) },
  { id: "act-6", issueId: "RL-1006", type: "detected", actor: "RoadLens detection", actorIsSystem: true, message: "Alligator crack flagged on Eastmoor Blvd (high severity)", timestamp: hoursAgo(11) },
  { id: "act-7", issueId: null, type: "status", actor: "Crew B — Patching", actorIsSystem: false, message: "WO-231 moved to in progress", timestamp: hoursAgo(22) },
  { id: "act-8", issueId: "RL-1013", type: "note", actor: "M. Okafor", actorIsSystem: false, message: "Utility cut nearby — coordinate with water dept before patching", timestamp: daysAgo(1.4) },
];

export const NOTIFICATIONS: AppNotification[] = [
  { id: "n-1", title: "3 new high-priority detections", body: "Eastmoor and Riverside — review queue updated.", timestamp: hoursAgo(1.1), read: false, kind: "detection" },
  { id: "n-2", title: "WO-231 in progress", body: "Crew B started pothole repairs on Riverbend Pkwy.", timestamp: hoursAgo(5.2), read: false, kind: "work_order" },
  { id: "n-3", title: "Unit 03 offline 24h+", body: "No imagery received from Unit 03 since yesterday.", timestamp: hoursAgo(8.4), read: false, kind: "system" },
  { id: "n-4", title: "Weekly digest ready", body: "84 detections processed last week across 5 districts.", timestamp: daysAgo(1.2), read: true, kind: "system" },
];

export const INTEGRATIONS: Integration[] = [
  { id: "fleet-gateway", name: "Municipal Fleet Camera Gateway", category: "Fleet cameras", description: "Ingests imagery from city-owned vehicles fitted with RoadLens capture kits.", status: "connected", detail: "4 vehicles streaming · last sync 4 min ago" },
  { id: "sweeper-cams", name: "Street Sweeper Cameras", category: "Fleet cameras", description: "Forward-facing cameras on the sweeper fleet, uploaded at end of route.", status: "connected", detail: "1 vehicle · nightly batch upload" },
  { id: "dashcam-partner", name: "Authorized Dashcam Program", category: "Dashcam providers", description: "Opt-in program for contracted commercial fleets. Only enrolled, consented vehicles contribute imagery.", status: "available", detail: "Requires signed data-sharing agreement" },
  { id: "arcgis", name: "ArcGIS Online", category: "GIS", description: "Publish confirmed detections and work-order layers to your GIS portal.", status: "connected", detail: "Feature layer synced hourly" },
  { id: "qgis-export", name: "GeoJSON / Shapefile Export", category: "GIS", description: "Scheduled exports for QGIS and other desktop GIS tools.", status: "available", detail: "Not configured" },
  { id: "cityworks", name: "Cityworks AMS", category: "Asset management", description: "Two-way sync of work orders with your asset-management system.", status: "attention", detail: "Token expires in 6 days" },
  { id: "cartegraph", name: "Cartegraph OMS", category: "Asset management", description: "Push approved work orders to Cartegraph operations management.", status: "available", detail: "Not configured" },
  { id: "webhooks", name: "Webhooks", category: "Developer", description: "Receive JSON events for new detections, reviews, and work-order changes.", status: "connected", detail: "2 endpoints active" },
  { id: "api", name: "REST API", category: "Developer", description: "Read access to detections, districts, and reports with scoped API keys.", status: "available", detail: "Keys managed by administrators" },
];

export const TEAM: TeamMember[] = [
  { id: "u-1", name: "Maya Okafor", email: "m.okafor@meridianfalls.example.gov", role: "Admin", lastActive: hoursAgo(0.5) },
  { id: "u-2", name: "Jonah Reyes", email: "j.reyes@meridianfalls.example.gov", role: "Supervisor", lastActive: hoursAgo(2.1) },
  { id: "u-3", name: "Tove Lindqvist", email: "t.lindqvist@meridianfalls.example.gov", role: "Engineer", lastActive: hoursAgo(6.7) },
  { id: "u-4", name: "Aaron Whitfield", email: "a.whitfield@meridianfalls.example.gov", role: "Inspector", lastActive: daysAgo(1.1) },
  { id: "u-5", name: "Priya Raman", email: "p.raman@meridianfalls.example.gov", role: "Viewer", lastActive: daysAgo(4) },
];

export const AUDIT_LOG: AuditEntry[] = [
  { id: "a-1", actor: "Maya Okafor", action: "Updated priority weights", target: "Settings › Prioritization", timestamp: hoursAgo(3.2), ip: "10.20.4.18" },
  { id: "a-2", actor: "Jonah Reyes", action: "Created work order", target: "WO-234", timestamp: hoursAgo(4.1), ip: "10.20.4.31" },
  { id: "a-3", actor: "Aaron Whitfield", action: "Rejected detection", target: "RL-1017", timestamp: hoursAgo(9.5), ip: "10.20.7.2" },
  { id: "a-4", actor: "Maya Okafor", action: "Invited team member", target: "p.raman@meridianfalls.example.gov", timestamp: daysAgo(4.2), ip: "10.20.4.18" },
  { id: "a-5", actor: "System", action: "Rotated webhook signing secret", target: "Integrations › Webhooks", timestamp: daysAgo(6), ip: "—" },
  { id: "a-6", actor: "Tove Lindqvist", action: "Exported issues CSV", target: "Reports", timestamp: daysAgo(8.5), ip: "10.20.5.44" },
];
