import type { District } from "@/lib/types";

/**
 * Fictional districts for the City of Meridian Falls demo municipality.
 * Boundaries are simple polygons ([lng, lat]) positioned over a real
 * street grid so the base map renders believable roads.
 */
export const DISTRICTS: District[] = [
  {
    id: "riverside",
    name: "Riverside",
    centroid: [-83.022, 39.963],
    laneMiles: 214,
    boundary: [
      [-83.038, 39.948],
      [-83.04, 39.972],
      [-83.03, 39.982],
      [-83.012, 39.978],
      [-83.008, 39.955],
      [-83.02, 39.945],
      [-83.038, 39.948],
    ],
  },
  {
    id: "north-end",
    name: "North End",
    centroid: [-82.998, 39.992],
    laneMiles: 187,
    boundary: [
      [-83.03, 39.982],
      [-83.018, 40.004],
      [-82.988, 40.008],
      [-82.972, 39.995],
      [-82.982, 39.98],
      [-83.012, 39.978],
      [-83.03, 39.982],
    ],
  },
  {
    id: "capitol",
    name: "Capitol District",
    centroid: [-82.998, 39.965],
    laneMiles: 96,
    boundary: [
      [-83.012, 39.978],
      [-82.982, 39.98],
      [-82.978, 39.958],
      [-82.995, 39.951],
      [-83.008, 39.955],
      [-83.012, 39.978],
    ],
  },
  {
    id: "eastmoor",
    name: "Eastmoor",
    centroid: [-82.962, 39.966],
    laneMiles: 243,
    boundary: [
      [-82.982, 39.98],
      [-82.972, 39.995],
      [-82.944, 39.99],
      [-82.94, 39.952],
      [-82.962, 39.946],
      [-82.978, 39.958],
      [-82.982, 39.98],
    ],
  },
  {
    id: "south-yards",
    name: "South Yards",
    centroid: [-82.99, 39.938],
    laneMiles: 158,
    boundary: [
      [-83.02, 39.945],
      [-83.008, 39.955],
      [-82.995, 39.951],
      [-82.978, 39.958],
      [-82.962, 39.946],
      [-82.968, 39.922],
      [-83.012, 39.925],
      [-83.02, 39.945],
    ],
  },
];

export const districtById = (id: string) =>
  DISTRICTS.find((d) => d.id === id) ?? DISTRICTS[0];
