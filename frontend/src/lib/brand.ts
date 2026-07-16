/**
 * Central product metadata. Change the product name, tagline, or
 * positioning copy here and it propagates across the marketing site
 * and the application chrome.
 */
export const BRAND = {
  name: "RoadLens",
  legalName: "RoadLens, Inc.",
  tagline: "Street-level intelligence for road maintenance",
  description:
    "RoadLens helps local governments detect, review, and prioritize road damage from ground-level fleet imagery — turning routine vehicle routes into a continuously updated maintenance plan.",
  domain: "roadlens.example",
  supportEmail: "hello@roadlens.example",
} as const;

/** Demo municipality shown throughout the prototype. Clearly fictional. */
export const DEMO_MUNICIPALITY = {
  id: "meridian-falls",
  name: "City of Meridian Falls",
  state: "OH",
  shortName: "Meridian Falls",
  center: [-83.0007, 39.9622] as [number, number],
  zoom: 12.4,
} as const;

export const OTHER_MUNICIPALITIES = [
  { id: "port-hollis", name: "Port Hollis", state: "MI", provisioned: false },
  { id: "kesler-county", name: "Kesler County DOT", state: "PA", provisioned: false },
] as const;
