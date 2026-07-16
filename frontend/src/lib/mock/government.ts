import type {
  CitizenReport,
  ConditionGrade,
  ExecutiveSummary,
  RoadSegment,
} from "@/lib/types";
import { DISTRICTS } from "./districts";
import { ISSUES } from "./issues";
import { daysAgo, hoursAgo, mulberry32, pick } from "./seed";

/* ------------------------------------------------------------------ */
/* Road network condition (segment-level, clearly fictional)           */
/* ------------------------------------------------------------------ */

const SEGMENT_STREETS: Record<string, string[]> = {
  riverside: ["Harlan Ave", "Riverbend Pkwy", "W Mill Rd", "Old Quarry Rd", "Cooper St"],
  "north-end": ["Winslow Blvd", "Calloway Ave", "N 9th St", "Foundry Rd"],
  capitol: ["Meridian Ave", "Court St", "Union St"],
  eastmoor: ["Eastmoor Blvd", "Colfax Ave", "Brantley Rd", "Pinehurst Dr"],
  "south-yards": ["S Canal St", "Yardline Rd", "Delaney St", "Wharton Ave"],
};

export function gradeForScore(score: number): ConditionGrade {
  if (score >= 85) return "A";
  if (score >= 70) return "B";
  if (score >= 55) return "C";
  if (score >= 40) return "D";
  return "F";
}

function buildSegments(): RoadSegment[] {
  const rand = mulberry32(9042026);
  const segments: RoadSegment[] = [];
  let counter = 101;

  for (const district of DISTRICTS) {
    for (const street of SEGMENT_STREETS[district.id]) {
      // Districts with more open issues trend toward lower condition.
      const issueLoad = ISSUES.filter(
        (i) => i.district === district.id && i.reviewStatus !== "rejected",
      ).length;
      const base = 88 - issueLoad * 3 - rand() * 30;
      const conditionScore = Math.max(24, Math.min(96, Math.round(base)));
      segments.push({
        id: `SEG-${counter++}`,
        streetName: street,
        district: district.id,
        lengthMiles: Math.round((0.4 + rand() * 2.6) * 10) / 10,
        conditionScore,
        grade: gradeForScore(conditionScore),
        openIssues: Math.round(rand() * 5 + (conditionScore < 55 ? 2 : 0)),
        lastInspected: daysAgo(Math.round(rand() * 45 + 2)),
        trend:
          conditionScore < 50
            ? pick(rand, ["declining", "declining", "stable"] as const)
            : pick(rand, ["improving", "stable", "stable"] as const),
      });
    }
  }
  return segments.sort((a, b) => a.conditionScore - b.conditionScore);
}

export const ROAD_SEGMENTS: RoadSegment[] = buildSegments();

/* ------------------------------------------------------------------ */
/* Citizen reports (311-style intake)                                  */
/* ------------------------------------------------------------------ */

export const CITIZEN_REPORTS: CitizenReport[] = [
  {
    id: "CR-131",
    description: "Deep pothole near the bus stop — hit it this morning, felt like it could damage a tire.",
    category: "Pothole",
    locationText: "Riverbend Pkwy at Cooper St",
    coordinates: [-83.0235, 39.9648],
    district: "riverside",
    submittedAt: hoursAgo(2.4),
    channel: "Mobile app",
    status: "new",
    matchedIssueId: null,
    photoSeed: 5011,
  },
  {
    id: "CR-130",
    description: "Long crack running down the middle of the lane for about half a block.",
    category: "Cracked pavement",
    locationText: "2100 block of Winslow Blvd",
    coordinates: [-82.9968, 39.9931],
    district: "north-end",
    submittedAt: hoursAgo(5.1),
    channel: "Web portal",
    status: "new",
    matchedIssueId: null,
    photoSeed: 5012,
  },
  {
    id: "CR-129",
    description: "Road surface is crumbling near the loading docks. Trucks are swerving around it.",
    category: "Pavement failure",
    locationText: "S Canal St near Freight House Ln",
    coordinates: [-82.9931, 39.9351],
    district: "south-yards",
    submittedAt: hoursAgo(9.7),
    channel: "311 call",
    status: "new",
    matchedIssueId: null,
    photoSeed: null,
  },
  {
    id: "CR-127",
    description: "Pothole reported after last week's rain. Getting bigger.",
    category: "Pothole",
    locationText: "Eastmoor Blvd at Sycamore St",
    coordinates: [-82.9605, 39.9663],
    district: "eastmoor",
    submittedAt: daysAgo(1.3),
    channel: "Mobile app",
    status: "matched",
    matchedIssueId: ISSUES[4]?.id ?? null,
    photoSeed: 5013,
  },
  {
    id: "CR-125",
    description: "Alligator cracking across both lanes, water pooling in it.",
    category: "Cracked pavement",
    locationText: "Colfax Ave near Brantley Rd",
    coordinates: [-82.9648, 39.9701],
    district: "eastmoor",
    submittedAt: daysAgo(2.1),
    channel: "Web portal",
    status: "converted",
    matchedIssueId: ISSUES[6]?.id ?? null,
    photoSeed: 5014,
  },
  {
    id: "CR-122",
    description: "Rough patch by the school crossing — repaired last month, looks good now.",
    category: "Pothole",
    locationText: "Garfield Pl at S 3rd St",
    coordinates: [-82.999, 39.9612],
    district: "capitol",
    submittedAt: daysAgo(6.5),
    channel: "311 call",
    status: "closed",
    matchedIssueId: null,
    photoSeed: null,
  },
];

/* ------------------------------------------------------------------ */
/* Executive summary                                                   */
/* ------------------------------------------------------------------ */

export const EXECUTIVE_SUMMARY: ExecutiveSummary = {
  conditionScore: 67,
  conditionDelta: 2,
  budget: {
    fiscalYear: "FY 2026",
    allocated: 2_400_000,
    committed: 1_310_000,
    spent: 962_000,
  },
  response: [
    { severity: "severe", medianDaysToReview: 0.6, medianDaysToRepair: 4 },
    { severity: "high", medianDaysToReview: 1.4, medianDaysToRepair: 12 },
    { severity: "moderate", medianDaysToReview: 3.1, medianDaysToRepair: 31 },
    { severity: "low", medianDaysToReview: 5.8, medianDaysToRepair: 74 },
  ],
  backlogTrend: [
    { label: "Aug", backlog: 731_000 },
    { label: "Sep", backlog: 748_000 },
    { label: "Oct", backlog: 771_000 },
    { label: "Nov", backlog: 760_000 },
    { label: "Dec", backlog: 742_000 },
    { label: "Jan", backlog: 803_000 },
    { label: "Feb", backlog: 886_000 },
    { label: "Mar", backlog: 914_000 },
    { label: "Apr", backlog: 868_000 },
    { label: "May", backlog: 812_000 },
    { label: "Jun", backlog: 764_000 },
    { label: "Jul", backlog: 738_000 },
  ],
  highlights: [
    "Backlog is down 19% from its March peak after the spring patching program.",
    "Severe detections are reviewed in under a day and repaired in a median of 4 days.",
    "Eastmoor remains the weakest district; 3 of its arterial segments grade D or F.",
    "Fleet coverage reached 68% of lane-miles this quarter (+4 pts), driven by the refuse-fleet integration.",
  ],
};
