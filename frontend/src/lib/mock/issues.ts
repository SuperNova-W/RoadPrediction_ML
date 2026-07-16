import type {
  BoundingBox,
  DamageClassCode,
  Detection,
  ReviewStatus,
  RoadIssue,
  Severity,
} from "@/lib/types";
import { DISTRICTS } from "./districts";
import { VEHICLES } from "./vehicles";
import { MOCK_NOW, mulberry32, pick } from "./seed";

/**
 * Deterministic, clearly fictional demo detections for Meridian Falls.
 * Generated with a seeded PRNG so IDs, positions, and scores are stable.
 */

const STREETS: Record<string, string[]> = {
  riverside: [
    "Harlan Ave",
    "W Mill Rd",
    "Beckett St",
    "Old Quarry Rd",
    "Riverbend Pkwy",
    "Cooper St",
  ],
  "north-end": [
    "N 9th St",
    "Calloway Ave",
    "Foundry Rd",
    "Larkspur Ln",
    "Winslow Blvd",
  ],
  capitol: ["Meridian Ave", "Court St", "S 3rd St", "Garfield Pl", "Union St"],
  eastmoor: [
    "Eastmoor Blvd",
    "Pinehurst Dr",
    "Colfax Ave",
    "Brantley Rd",
    "Sycamore St",
  ],
  "south-yards": [
    "Yardline Rd",
    "Delaney St",
    "Freight House Ln",
    "S Canal St",
    "Wharton Ave",
  ],
};

const CLASS_SEQUENCE: DamageClassCode[] = [
  "D40", "D20", "D00", "D40", "D10", "D00", "D20", "D40",
  "D00", "D20", "D10", "D40", "D00", "D20", "D40", "D10",
  "D00", "D20", "D40", "D00", "D10", "D20", "D40", "D00",
  "D20", "D40", "D00", "D10",
];

const SEVERITY_BY_CLASS: Record<DamageClassCode, Severity[]> = {
  D00: ["low", "low", "moderate", "moderate", "high"],
  D10: ["low", "moderate", "moderate", "high"],
  D20: ["moderate", "moderate", "high", "high", "severe"],
  D40: ["moderate", "high", "high", "severe", "severe"],
};

const SEVERITY_WEIGHT: Record<Severity, number> = {
  low: 18,
  moderate: 42,
  high: 66,
  severe: 86,
};

const CLASS_WEIGHT: Record<DamageClassCode, number> = {
  D00: 0,
  D10: 2,
  D20: 6,
  D40: 10,
};

const COST_BASE: Record<DamageClassCode, number> = {
  D00: 900,
  D10: 1100,
  D20: 4200,
  D40: 2600,
};

const REVIEWERS = ["M. Okafor", "J. Reyes", "T. Lindqvist", "A. Whitfield"];

function primaryBox(rand: () => number, code: DamageClassCode): BoundingBox {
  // Boxes sit in the lower 2/3 of the frame where pavement appears.
  switch (code) {
    case "D00":
      return { x: 0.3 + rand() * 0.3, y: 0.42 + rand() * 0.1, width: 0.1 + rand() * 0.08, height: 0.4 + rand() * 0.15 };
    case "D10":
      return { x: 0.15 + rand() * 0.15, y: 0.55 + rand() * 0.2, width: 0.5 + rand() * 0.25, height: 0.1 + rand() * 0.08 };
    case "D20":
      return { x: 0.2 + rand() * 0.25, y: 0.5 + rand() * 0.15, width: 0.3 + rand() * 0.2, height: 0.28 + rand() * 0.15 };
    case "D40":
      return { x: 0.3 + rand() * 0.3, y: 0.55 + rand() * 0.2, width: 0.16 + rand() * 0.12, height: 0.14 + rand() * 0.1 };
  }
}

function buildIssues(): RoadIssue[] {
  const rand = mulberry32(20260715);
  const issues: RoadIssue[] = [];
  const districtIds = DISTRICTS.map((d) => d.id);

  for (let i = 0; i < CLASS_SEQUENCE.length; i++) {
    const classCode = CLASS_SEQUENCE[i];
    const district = DISTRICTS[i % districtIds.length];
    const severity = pick(rand, SEVERITY_BY_CLASS[classCode]);
    const confidence = Math.round((0.62 + rand() * 0.35) * 100) / 100;
    const trafficFactor = rand() * 14; // stand-in for road importance
    const priorityScore = Math.min(
      98,
      Math.round(
        SEVERITY_WEIGHT[severity] +
          CLASS_WEIGHT[classCode] +
          confidence * 8 +
          trafficFactor,
      ),
    );

    const reviewRoll = rand();
    const reviewStatus: ReviewStatus =
      reviewRoll < 0.48 ? "pending" : reviewRoll < 0.85 ? "confirmed" : "rejected";

    const capturedAt = new Date(
      MOCK_NOW - Math.floor(rand() * 30 * 24 + 2) * 3600_000,
    ).toISOString();

    const detections: Detection[] = [
      {
        id: `det-${i + 1}-1`,
        classCode,
        confidence,
        box: primaryBox(rand, classCode),
      },
    ];
    if (rand() > 0.62) {
      const secondary: DamageClassCode = classCode === "D00" ? "D10" : "D00";
      detections.push({
        id: `det-${i + 1}-2`,
        classCode: secondary,
        confidence: Math.round((0.55 + rand() * 0.25) * 100) / 100,
        box: primaryBox(rand, secondary),
      });
    }

    const [clng, clat] = district.centroid;
    issues.push({
      id: `RL-${1001 + i}`,
      coordinates: [
        Math.round((clng + (rand() - 0.5) * 0.024) * 1e5) / 1e5,
        Math.round((clat + (rand() - 0.5) * 0.02) * 1e5) / 1e5,
      ],
      roadName: `${100 + Math.floor(rand() * 48) * 100} ${pick(rand, STREETS[district.id])}`,
      district: district.id,
      classCode,
      confidence,
      severity,
      priorityScore,
      reviewStatus,
      workOrderId: null, // linked from work-orders.ts
      capturedAt,
      vehicleId: pick(rand, VEHICLES.slice(0, 4)).id,
      imageSeed: 7000 + i * 13,
      detections,
      assignee:
        reviewStatus === "confirmed" && rand() > 0.4 ? pick(rand, REVIEWERS) : null,
      estRepairCost:
        Math.round(
          (COST_BASE[classCode] * (0.7 + rand() * 0.9) * (SEVERITY_WEIGHT[severity] / 42)) /
            50,
        ) * 50,
    });
  }

  return issues.sort((a, b) => b.priorityScore - a.priorityScore);
}

export const ISSUES: RoadIssue[] = buildIssues();
