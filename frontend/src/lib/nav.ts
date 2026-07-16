import {
  BarChart3,
  ClipboardList,
  Landmark,
  LayoutDashboard,
  ListChecks,
  Map,
  Megaphone,
  Plug,
  Settings,
  UploadCloud,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

/** Central navigation configuration for the authenticated app. */
export const APP_NAV: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard, description: "Network health, KPIs, and recent detections" },
  { label: "Executive brief", href: "/executive", icon: Landmark, description: "Budget, backlog, and response times for leadership" },
  { label: "Issues", href: "/issues", icon: ListChecks, description: "Review and triage detected road damage" },
  { label: "Map", href: "/map", icon: Map, description: "Full-screen operational map" },
  { label: "Road network", href: "/network", icon: Waypoints, description: "Street-segment condition grades" },
  { label: "Citizen reports", href: "/citizen-reports", icon: Megaphone, description: "311 intake matched to AI detections" },
  { label: "Ingestion", href: "/ingestion", icon: UploadCloud, description: "Upload imagery and monitor fleet capture" },
  { label: "Work orders", href: "/work-orders", icon: ClipboardList, description: "Plan and track repairs" },
  { label: "Analytics", href: "/analytics", icon: BarChart3, description: "Performance measures, drill-downs, benchmarks, exports" },
  { label: "Integrations", href: "/integrations", icon: Plug, description: "Cameras, GIS, and asset systems" },
  { label: "Settings", href: "/settings", icon: Settings, description: "Municipality, team, thresholds, audit" },
];

export const MARKETING_NAV = [
  { label: "Product", href: "#product" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Government", href: "#government" },
  { label: "Security", href: "#security" },
] as const;
