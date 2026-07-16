import {
  BarChart3,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Map,
  Plug,
  Settings,
  UploadCloud,
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
  { label: "Issues", href: "/issues", icon: ListChecks, description: "Review and triage detected road damage" },
  { label: "Map", href: "/map", icon: Map, description: "Full-screen operational map" },
  { label: "Ingestion", href: "/ingestion", icon: UploadCloud, description: "Upload imagery and monitor fleet capture" },
  { label: "Work orders", href: "/work-orders", icon: ClipboardList, description: "Plan and track repairs" },
  { label: "Reports", href: "/reports", icon: BarChart3, description: "Trends, comparisons, and exports" },
  { label: "Integrations", href: "/integrations", icon: Plug, description: "Cameras, GIS, and asset systems" },
  { label: "Settings", href: "/settings", icon: Settings, description: "Municipality, team, thresholds, audit" },
];

export const MARKETING_NAV = [
  { label: "Product", href: "#product" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Government", href: "#government" },
  { label: "Security", href: "#security" },
] as const;
