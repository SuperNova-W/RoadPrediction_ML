import type { PeerBenchmark, PerformanceMeasure } from "@/lib/types";

/**
 * Performance measures in the open-performance style used by
 * government analytics platforms: every measure carries a target,
 * a status computed against it, its reporting period, and a
 * plain-language rationale. All values are fictional demo data.
 */
export const PERFORMANCE_MEASURES: PerformanceMeasure[] = [
  {
    id: "severe-7d",
    name: "Severe damage repaired within 7 days",
    whyItMatters:
      "Severe defects are the ones most likely to damage vehicles or cause claims. This tracks how often the city closes them within its own 7-day standard.",
    value: 0.86,
    format: "percent",
    target: 0.9,
    direction: "at_or_above",
    status: "watch",
    yoyDelta: "+9 pts vs FY25",
    yoyIsImprovement: true,
    periodLabel: "Q2 FY26 (Apr–Jun)",
    updatedNote: "Updated nightly from work-order closures",
    spark: [0.71, 0.74, 0.72, 0.78, 0.81, 0.8, 0.84, 0.86],
  },
  {
    id: "median-repair",
    name: "Median days to repair — severe",
    whyItMatters:
      "Time from a confirmed severe detection to completed repair. Shorter is safer and usually cheaper than deferred patching.",
    value: 4,
    format: "days",
    target: 5,
    direction: "at_or_below",
    status: "on_track",
    yoyDelta: "-3.5 days vs FY25",
    yoyIsImprovement: true,
    periodLabel: "Q2 FY26 (Apr–Jun)",
    updatedNote: "Updated nightly from work-order closures",
    spark: [8.5, 8, 7.5, 6.5, 6, 5, 4.5, 4],
  },
  {
    id: "condition-score",
    name: "Network condition score",
    whyItMatters:
      "Length-weighted average condition of monitored segments (0–100). A heuristic from fleet imagery — not a certified PCI survey.",
    value: 67,
    format: "score",
    target: 70,
    direction: "at_or_above",
    status: "watch",
    yoyDelta: "+2 pts vs FY25",
    yoyIsImprovement: true,
    periodLabel: "Q2 FY26 (Apr–Jun)",
    updatedNote: "Recomputed weekly from repeated passes",
    spark: [63, 63, 64, 64, 65, 66, 66, 67],
  },
  {
    id: "backlog-mile",
    name: "Backlog per lane-mile",
    whyItMatters:
      "Estimated open repair cost divided by monitored lane-miles. Normalizing by mileage makes quarters and peer cities comparable.",
    value: 575,
    format: "currency",
    unitSuffix: "/ lane-mile",
    target: 600,
    direction: "at_or_below",
    status: "on_track",
    yoyDelta: "-12% vs FY25",
    yoyIsImprovement: true,
    periodLabel: "Q2 FY26 (Apr–Jun)",
    updatedNote: "Updated nightly from open confirmed issues",
    spark: [655, 668, 690, 712, 676, 640, 601, 575],
  },
];

/**
 * Fictional peer cohort for benchmarking (population 60–120k, similar
 * winters). Real deployments would use ICMA/APWA-style cohort data.
 */
export const PEER_BENCHMARK: PeerBenchmark = {
  measureLabel: "Backlog per lane-mile",
  unit: "$",
  cohortNote:
    "Fictional peer cohort for the demo — cities of 60–120k population with comparable freeze–thaw exposure. Production deployments benchmark against ICMA/APWA-style datasets.",
  rows: [
    { name: "Cedar Vale", value: 540, isSelf: false },
    { name: "Meridian Falls", value: 575, isSelf: true },
    { name: "Harlow Springs", value: 612, isSelf: false },
    { name: "Port Hollis", value: 655, isSelf: false },
    { name: "Bexton", value: 698, isSelf: false },
  ],
};
