import type { FleetVehicle } from "@/lib/types";
import { hoursAgo } from "./seed";

export const VEHICLES: FleetVehicle[] = [
  {
    id: "unit-12",
    name: "Unit 12",
    kind: "Public works pickup — cab-mounted camera",
    status: "active",
    lastSeen: hoursAgo(0.1),
    milesToday: 42.6,
    imagesToday: 1184,
    district: "riverside",
  },
  {
    id: "unit-07",
    name: "Unit 07",
    kind: "Street sweeper — forward camera",
    status: "active",
    lastSeen: hoursAgo(0.4),
    milesToday: 28.1,
    imagesToday: 806,
    district: "north-end",
  },
  {
    id: "unit-19",
    name: "Unit 19",
    kind: "Inspection SUV — dual camera",
    status: "idle",
    lastSeen: hoursAgo(2.2),
    milesToday: 17.4,
    imagesToday: 512,
    district: "eastmoor",
  },
  {
    id: "refuse-04",
    name: "Refuse 04",
    kind: "Refuse truck — authorized fleet integration",
    status: "active",
    lastSeen: hoursAgo(0.2),
    milesToday: 33.9,
    imagesToday: 947,
    district: "south-yards",
  },
  {
    id: "unit-03",
    name: "Unit 03",
    kind: "Public works van — cab-mounted camera",
    status: "offline",
    lastSeen: hoursAgo(26),
    milesToday: 0,
    imagesToday: 0,
    district: "capitol",
  },
];

export const vehicleById = (id: string) =>
  VEHICLES.find((v) => v.id === id) ?? VEHICLES[0];
