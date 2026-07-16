import type { WorkOrder } from "@/lib/types";
import { ISSUES } from "./issues";
import { daysAgo, daysAhead } from "./seed";

const CREWS = [
  "Crew A — Asphalt",
  "Crew B — Patching",
  "Northside Paving Co. (contract)",
  "Crew C — Concrete",
  "Halloway Rd. Services (contract)",
];

/** Hand-curated work orders linked to real issues in the mock dataset. */
function buildWorkOrders(): WorkOrder[] {
  const confirmed = ISSUES.filter((i) => i.reviewStatus === "confirmed");
  const take = (n: number, offset: number) =>
    confirmed.slice(offset, offset + n).map((i) => i.id);

  const orders: WorkOrder[] = [
    {
      id: "WO-231",
      title: "Pothole repairs — Riverside arterials",
      issueIds: take(2, 0),
      status: "in_progress",
      crew: CREWS[1],
      costEstimate: 8400,
      dueDate: daysAhead(4),
      createdAt: daysAgo(9),
      district: "riverside",
      priority: "severe",
    },
    {
      id: "WO-232",
      title: "Alligator crack patching — Eastmoor Blvd corridor",
      issueIds: take(2, 2),
      status: "scheduled",
      crew: CREWS[2],
      costEstimate: 12600,
      dueDate: daysAhead(11),
      createdAt: daysAgo(7),
      district: "eastmoor",
      priority: "high",
    },
    {
      id: "WO-233",
      title: "Crack sealing batch — North End residentials",
      issueIds: take(3, 4),
      status: "approved",
      crew: CREWS[0],
      costEstimate: 5200,
      dueDate: daysAhead(18),
      createdAt: daysAgo(5),
      district: "north-end",
      priority: "moderate",
    },
    {
      id: "WO-234",
      title: "Pothole + base repair — S Canal St",
      issueIds: take(1, 7),
      status: "planned",
      crew: "Unassigned",
      costEstimate: 3900,
      dueDate: daysAhead(25),
      createdAt: daysAgo(3),
      district: "south-yards",
      priority: "high",
    },
    {
      id: "WO-235",
      title: "Transverse crack sealing — Capitol district",
      issueIds: take(2, 8),
      status: "completed",
      crew: CREWS[0],
      costEstimate: 4100,
      dueDate: daysAgo(6),
      createdAt: daysAgo(21),
      district: "capitol",
      priority: "moderate",
    },
    {
      id: "WO-236",
      title: "Emergency pothole response — Winslow Blvd",
      issueIds: take(1, 10),
      status: "completed",
      crew: CREWS[1],
      costEstimate: 2200,
      dueDate: daysAgo(12),
      createdAt: daysAgo(15),
      district: "north-end",
      priority: "severe",
    },
    {
      id: "WO-237",
      title: "Surface prep survey — Old Quarry Rd",
      issueIds: take(2, 11),
      status: "planned",
      crew: "Unassigned",
      costEstimate: 6800,
      dueDate: daysAhead(32),
      createdAt: daysAgo(1),
      district: "riverside",
      priority: "moderate",
    },
  ];

  // Backlink issues to their work orders.
  for (const order of orders) {
    for (const issueId of order.issueIds) {
      const issue = ISSUES.find((i) => i.id === issueId);
      if (issue) issue.workOrderId = order.id;
    }
  }

  return orders;
}

export const WORK_ORDERS: WorkOrder[] = buildWorkOrders();
