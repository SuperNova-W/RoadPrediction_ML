"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Flame, Layers, X } from "lucide-react";
import { ClassBadge, PriorityScore, ReviewBadge, SeverityBadge } from "@/components/domain/badges";
import { DetectionOverlay } from "@/components/domain/detection-overlay";
import { RoadImage } from "@/components/domain/road-image";
import { IssueMap, type Basemap } from "@/components/map/issue-map";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { getDistricts, getIssues } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { MOCK_NOW } from "@/lib/mock/seed";
import { DAMAGE_CLASSES, type DamageClassCode } from "@/lib/types";
import { DAMAGE_COLORS } from "@/lib/tokens";
import { formatDate, formatDateTime } from "@/lib/format";
import { districtById } from "@/lib/mock/districts";

const CLASS_CODES = Object.keys(DAMAGE_CLASSES) as DamageClassCode[];
const WINDOW_DAYS = 30;

export default function MapPage() {
  const reduceMotion = useReducedMotion();
  const issues = useAsync(() => getIssues(), []);
  const districts = useAsync(() => getDistricts(), []);

  const [visibleClasses, setVisibleClasses] = React.useState<DamageClassCode[]>(CLASS_CODES);
  const [heatmap, setHeatmap] = React.useState(false);
  const [basemap, setBasemap] = React.useState<Basemap>("streets");
  const [showDistricts, setShowDistricts] = React.useState(true);
  const [timePct, setTimePct] = React.useState(100);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const windowStart = MOCK_NOW - WINDOW_DAYS * 86400_000;
  const maxTimestamp = windowStart + ((MOCK_NOW - windowStart) * timePct) / 100;
  const selected = (issues.data ?? []).find((i) => i.id === selectedId) ?? null;

  return (
    <div className="relative h-[calc(100dvh-3.5rem)] w-full overflow-hidden">
      {issues.loading || districts.loading ? (
        <Skeleton className="h-full w-full rounded-none" />
      ) : (
        <IssueMap
          issues={issues.data ?? []}
          districts={districts.data ?? []}
          showDistricts={showDistricts}
          showHeatmap={heatmap}
          visibleClasses={visibleClasses}
          maxTimestamp={maxTimestamp}
          selectedId={selectedId}
          onSelect={setSelectedId}
          basemap={basemap}
          className="rounded-none"
        />
      )}

      {/* Layer controls */}
      <div className="absolute left-4 top-4 w-60 rounded-lg border bg-card/95 p-4 shadow-raised backdrop-blur">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <Layers className="h-4 w-4 text-muted-foreground" aria-hidden />
          Layers
        </p>

        {/* Basemap switch */}
        <div
          className="mt-3 grid grid-cols-2 gap-1 rounded-md bg-muted p-1"
          role="group"
          aria-label="Basemap"
        >
          {(
            [
              ["streets", "Streets"],
              ["satellite", "Satellite"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setBasemap(value)}
              aria-pressed={basemap === value}
              className={
                basemap === value
                  ? "rounded bg-card px-2 py-1 text-xs font-semibold shadow-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  : "rounded px-2 py-1 text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              }
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mt-3 space-y-2" role="group" aria-label="Damage type layers">
          {CLASS_CODES.map((code) => (
            <label key={code} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox
                checked={visibleClasses.includes(code)}
                onCheckedChange={(checked) =>
                  setVisibleClasses((prev) =>
                    checked ? [...prev, code] : prev.filter((c) => c !== code),
                  )
                }
                aria-label={DAMAGE_CLASSES[code].label}
              />
              <span
                className="h-2.5 w-2.5 rounded-full ring-2 ring-card"
                style={{ backgroundColor: DAMAGE_COLORS[code] }}
                aria-hidden
              />
              <span className="font-medium">{DAMAGE_CLASSES[code].label}</span>
            </label>
          ))}
        </div>
        <div className="mt-4 space-y-3 border-t pt-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="heatmap-toggle" className="flex items-center gap-1.5 text-sm">
              <Flame className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              Heatmap
            </Label>
            <Switch id="heatmap-toggle" checked={heatmap} onCheckedChange={setHeatmap} />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="district-toggle" className="text-sm">
              District boundaries
            </Label>
            <Switch
              id="district-toggle"
              checked={showDistricts}
              onCheckedChange={setShowDistricts}
            />
          </div>
        </div>
      </div>

      {/* Time slider */}
      <div className="absolute bottom-6 left-1/2 w-[min(480px,calc(100%-2rem))] -translate-x-1/2 rounded-lg border bg-card/95 px-5 py-3 shadow-raised backdrop-blur">
        <div className="flex items-baseline justify-between text-xs text-muted-foreground">
          <span>Detections through</span>
          <span className="tnum font-medium text-foreground">
            {formatDate(new Date(maxTimestamp).toISOString())}
          </span>
        </div>
        <Slider
          value={[timePct]}
          onValueChange={([v]) => setTimePct(v)}
          max={100}
          step={2}
          className="mt-2"
          aria-label="Time window"
        />
        <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
          <span>{formatDate(new Date(windowStart).toISOString())}</span>
          <span>Today</span>
        </div>
      </div>

      {/* Detail drawer */}
      <AnimatePresence>
        {selected && (
          <motion.aside
            key={selected.id}
            initial={reduceMotion ? false : { x: 340, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={reduceMotion ? undefined : { x: 340, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            className="absolute bottom-4 right-4 top-4 z-10 w-[min(360px,calc(100%-2rem))] overflow-y-auto rounded-lg border bg-card shadow-overlay"
            aria-label={`Issue ${selected.id} details`}
          >
            <div className="flex items-start justify-between p-4 pb-2">
              <div>
                <p className="tnum text-sm font-semibold">{selected.id}</p>
                <p className="text-sm text-muted-foreground">{selected.roadName}</p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setSelectedId(null)}
                aria-label="Close details"
              >
                <X className="h-4 w-4" aria-hidden />
              </Button>
            </div>
            <div className="relative mx-4 aspect-[8/5] overflow-hidden rounded-md border">
              <RoadImage seed={selected.imageSeed} classCode={selected.classCode} />
              <DetectionOverlay detections={selected.detections} showLabels={false} />
            </div>
            <div className="space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <ClassBadge code={selected.classCode} short />
                <SeverityBadge severity={selected.severity} />
                <ReviewBadge status={selected.reviewStatus} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Priority</p>
                  <PriorityScore score={selected.priorityScore} />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">District</p>
                  <p className="font-medium">{districtById(selected.district).name}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-xs text-muted-foreground">Captured</p>
                  <p className="font-medium">
                    {formatDateTime(selected.capturedAt)} · {selected.vehicleId}
                  </p>
                </div>
              </div>
              <Button className="w-full" asChild>
                <Link href={`/issues/${selected.id}`}>
                  Open issue <ArrowUpRight aria-hidden />
                </Link>
              </Button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}
