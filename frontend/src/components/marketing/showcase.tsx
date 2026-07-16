"use client";

import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { BarChart3, ClipboardList, ListOrdered, MapIcon } from "lucide-react";
import { ClassBadge, PriorityScore, SeverityBadge, WorkOrderBadge } from "@/components/domain/badges";
import { DetectionOverlay } from "@/components/domain/detection-overlay";
import { RoadImage } from "@/components/domain/road-image";
import { IssueMap } from "@/components/map/issue-map";
import { DamageDistributionChart } from "@/components/charts/charts";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ISSUES } from "@/lib/mock/issues";
import { DISTRICTS } from "@/lib/mock/districts";
import { WORK_ORDERS } from "@/lib/mock/work-orders";
import type { DamageClassCode } from "@/lib/types";
import { formatConfidence } from "@/lib/format";

/**
 * Marketing showcase: real product components framed as previews,
 * fed by the same mock service data as the app.
 */
export function ShowcaseTabs() {
  const reduceMotion = useReducedMotion();
  const featured = ISSUES[0];

  const distribution = React.useMemo(() => {
    const counts: Record<DamageClassCode, number> = { D00: 0, D10: 0, D20: 0, D40: 0 };
    for (const issue of ISSUES) counts[issue.classCode]++;
    return (Object.keys(counts) as DamageClassCode[]).map((code) => ({
      code,
      count: counts[code],
    }));
  }, []);

  return (
    <Tabs defaultValue="map">
      <div className="flex justify-center">
        <TabsList aria-label="Product previews" className="h-auto flex-wrap">
          <TabsTrigger value="map">
            <MapIcon aria-hidden /> Interactive map
          </TabsTrigger>
          <TabsTrigger value="review">
            <ClipboardList aria-hidden /> Damage review
          </TabsTrigger>
          <TabsTrigger value="queue">
            <ListOrdered aria-hidden /> Priority queue
          </TabsTrigger>
          <TabsTrigger value="reports">
            <BarChart3 aria-hidden /> Reports &amp; work orders
          </TabsTrigger>
        </TabsList>
      </div>

      <div className="mx-auto mt-6 max-w-4xl">
        <TabsContent value="map">
          <Frame label="Operational map — demo data">
            <div className="h-[380px]">
              <IssueMap issues={ISSUES} districts={DISTRICTS} showDistricts className="rounded-b-lg rounded-t-none" />
            </div>
          </Frame>
        </TabsContent>

        <TabsContent value="review">
          <Frame label={`Issue ${featured.id} — ${featured.roadName}`}>
            <div className="grid gap-4 p-4 sm:grid-cols-[3fr_2fr]">
              <div className="relative aspect-[8/5] overflow-hidden rounded-md border">
                <RoadImage seed={featured.imageSeed} classCode={featured.classCode} />
                <DetectionOverlay detections={featured.detections} />
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <ClassBadge code={featured.classCode} short />
                  <SeverityBadge severity={featured.severity} />
                </div>
                <Row k="Model confidence" v={formatConfidence(featured.confidence)} />
                <Row k="Priority score" v={`${featured.priorityScore} / 100`} />
                <Row k="Review status" v="Awaiting inspector" />
                <p className="rounded-md bg-muted p-3 text-xs leading-relaxed text-muted-foreground">
                  Inspectors confirm or reject each detection before it can be
                  scheduled — the AI proposes, your team decides.
                </p>
              </div>
            </div>
          </Frame>
        </TabsContent>

        <TabsContent value="queue">
          <Frame label="Repair-priority queue — demo data">
            <ul className="divide-y">
              {ISSUES.slice(0, 5).map((issue, i) => (
                <motion.li
                  key={issue.id}
                  initial={reduceMotion ? false : { opacity: 0, x: -14 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <PriorityScore score={issue.priorityScore} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{issue.roadName}</p>
                    <p className="text-xs text-muted-foreground">{issue.id}</p>
                  </div>
                  <span className="hidden sm:block">
                    <ClassBadge code={issue.classCode} short />
                  </span>
                  <SeverityBadge severity={issue.severity} />
                </motion.li>
              ))}
            </ul>
          </Frame>
        </TabsContent>

        <TabsContent value="reports">
          <Frame label="Reporting & work orders — demo data">
            <div className="grid gap-4 p-4 md:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Damage distribution
                </p>
                <DamageDistributionChart data={distribution} />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Active work orders
                </p>
                <ul className="space-y-2">
                  {WORK_ORDERS.slice(0, 4).map((order) => (
                    <li key={order.id} className="flex items-center gap-2 rounded-md border p-2.5">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{order.title}</p>
                        <p className="tnum text-xs text-muted-foreground">
                          {order.id} · ${order.costEstimate.toLocaleString()}
                        </p>
                      </div>
                      <WorkOrderBadge status={order.status} />
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Frame>
        </TabsContent>
      </div>
    </Tabs>
  );
}

function Frame({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card shadow-raised">
      <div className="flex items-center gap-2 border-b bg-muted/60 px-4 py-2">
        <span className="flex gap-1.5" aria-hidden>
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
        </span>
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Badge variant="muted" className="ml-auto">Mock data</Badge>
      </div>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted-foreground">{k}</span>
      <span className="tnum font-medium">{v}</span>
    </div>
  );
}
