"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { RoadImage } from "@/components/domain/road-image";
import { DAMAGE_COLORS } from "@/lib/tokens";
import { DAMAGE_CLASSES } from "@/lib/types";

/**
 * Looping hero animation: a captured frame is scanned, bounding boxes lock
 * on, and the detections become prioritized markers on a stylized city map.
 * With prefers-reduced-motion the final state renders statically.
 */

type Phase = "scan" | "boxes" | "map";

const BOXES = [
  { id: "b1", code: "D40" as const, x: 0.4, y: 0.62, w: 0.2, h: 0.16, conf: "91%" },
  { id: "b2", code: "D20" as const, x: 0.16, y: 0.5, w: 0.22, h: 0.2, conf: "84%" },
  { id: "b3", code: "D00" as const, x: 0.66, y: 0.46, w: 0.1, h: 0.34, conf: "77%" },
];

const MARKERS = [
  { id: "m1", code: "D40" as const, cx: 118, cy: 92, score: 88 },
  { id: "m2", code: "D20" as const, cx: 70, cy: 138, score: 71 },
  { id: "m3", code: "D00" as const, cx: 158, cy: 152, score: 54 },
];

export function HeroDemo() {
  const reduceMotion = useReducedMotion();
  const [phase, setPhase] = React.useState<Phase>(reduceMotion ? "map" : "scan");

  React.useEffect(() => {
    if (reduceMotion) return;
    const durations: Record<Phase, number> = { scan: 2100, boxes: 2100, map: 3600 };
    const next: Record<Phase, Phase> = { scan: "boxes", boxes: "map", map: "scan" };
    const t = setTimeout(() => setPhase((p) => next[p]), durations[phase]);
    return () => clearTimeout(t);
  }, [phase, reduceMotion]);

  const showBoxes = phase !== "scan" || reduceMotion;
  const showMarkers = phase === "map" || reduceMotion;

  return (
    <div
      className="grid gap-3 sm:grid-cols-[3fr_2fr]"
      aria-label="Animated illustration: road imagery is scanned, damage is boxed, and detections become prioritized map markers"
      role="img"
    >
      {/* Camera frame */}
      <div className="relative overflow-hidden rounded-xl border border-white/15 bg-navy shadow-overlay">
        <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-destructive/80" aria-hidden />
          <span className="h-2 w-2 rounded-full bg-warning/80" aria-hidden />
          <span className="h-2 w-2 rounded-full bg-success/80" aria-hidden />
          <p className="ml-2 truncate text-[11px] font-medium text-white/60">
            unit12_frame_4217.jpg · Riverbend Pkwy
          </p>
          <p className="ml-auto text-[10px] uppercase tracking-widest text-white/40">
            {phase === "scan" ? "Scanning" : phase === "boxes" ? "Detecting" : "Mapped"}
          </p>
        </div>
        <div className="relative aspect-[8/5]">
          <RoadImage seed={4217} classCode="D40" />

          {/* Scan beam */}
          {!reduceMotion && phase === "scan" && (
            <motion.div
              className="absolute inset-y-0 w-24"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(101,157,255,0.28), rgba(101,157,255,0.55), transparent)",
              }}
              initial={{ left: "-20%" }}
              animate={{ left: "110%" }}
              transition={{ duration: 1.9, ease: "easeInOut" }}
              aria-hidden
            >
              <div className="absolute inset-y-0 right-8 w-px bg-[#8ab4ff]" />
            </motion.div>
          )}

          {/* Bounding boxes */}
          <AnimatePresence>
            {showBoxes &&
              BOXES.map((box, i) => (
                <motion.div
                  key={box.id}
                  className="absolute"
                  style={{
                    left: `${box.x * 100}%`,
                    top: `${box.y * 100}%`,
                    width: `${box.w * 100}%`,
                    height: `${box.h * 100}%`,
                  }}
                  initial={reduceMotion ? { opacity: 1 } : { opacity: 0, scale: 1.3 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ delay: reduceMotion ? 0 : i * 0.22, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                  aria-hidden
                >
                  <div
                    className="absolute inset-0 rounded-sm"
                    style={{
                      border: `2px solid ${DAMAGE_COLORS[box.code]}`,
                      backgroundColor: `${DAMAGE_COLORS[box.code]}1f`,
                      boxShadow: "0 0 0 1px rgb(255 255 255 / 0.3)",
                    }}
                  />
                  <span
                    className="absolute -top-5 left-0 rounded px-1 py-px text-[9px] font-bold text-white"
                    style={{ backgroundColor: DAMAGE_COLORS[box.code] }}
                  >
                    {DAMAGE_CLASSES[box.code].short} {box.conf}
                  </span>
                </motion.div>
              ))}
          </AnimatePresence>
        </div>
      </div>

      {/* Stylized city map */}
      <div className="relative overflow-hidden rounded-xl border border-white/15 bg-[#101a2e] shadow-overlay">
        <div className="border-b border-white/10 px-3 py-2">
          <p className="text-[11px] font-medium text-white/60">Priority map · Meridian Falls</p>
        </div>
        <svg viewBox="0 0 220 200" className="h-full max-h-64 w-full sm:max-h-none" aria-hidden>
          {/* Road grid */}
          <g>
            {[28, 62, 96, 130, 164].map((y) => (
              <line key={`h${y}`} x1="0" y1={y} x2="220" y2={y} stroke="#26334d" strokeWidth={y === 96 ? 5 : 2.5} />
            ))}
            {[36, 78, 120, 162, 198].map((x) => (
              <line key={`v${x}`} x1={x} y1="0" x2={x} y2="200" stroke="#26334d" strokeWidth={x === 120 ? 5 : 2.5} />
            ))}
            <path d="M0 180 Q 80 150 220 175" fill="none" stroke="#26334d" strokeWidth="3.5" />
            <path d="M10 0 Q 60 70 30 200" fill="none" stroke="#223049" strokeWidth="2.5" />
          </g>
          {/* River */}
          <path
            d="M180 0 Q 150 60 190 120 T 170 200"
            fill="none"
            stroke="#1d3a52"
            strokeWidth="9"
            opacity="0.9"
          />

          {/* Markers */}
          {MARKERS.map((marker, i) => (
            <g key={marker.id}>
              {showMarkers && !reduceMotion ? (
                <>
                  <motion.circle
                    cx={marker.cx}
                    cy={marker.cy}
                    r="6"
                    fill={DAMAGE_COLORS[marker.code]}
                    stroke="#fff"
                    strokeWidth="1.5"
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.25 + i * 0.28, type: "spring", stiffness: 400, damping: 18 }}
                    style={{ transformOrigin: `${marker.cx}px ${marker.cy}px` }}
                  />
                  <motion.circle
                    cx={marker.cx}
                    cy={marker.cy}
                    r="6"
                    fill="none"
                    stroke={DAMAGE_COLORS[marker.code]}
                    initial={{ scale: 1, opacity: 0.8 }}
                    animate={{ scale: 2.6, opacity: 0 }}
                    transition={{ delay: 0.35 + i * 0.28, duration: 1.1, ease: "easeOut" }}
                    style={{ transformOrigin: `${marker.cx}px ${marker.cy}px` }}
                  />
                </>
              ) : showMarkers ? (
                <circle
                  cx={marker.cx}
                  cy={marker.cy}
                  r="6"
                  fill={DAMAGE_COLORS[marker.code]}
                  stroke="#fff"
                  strokeWidth="1.5"
                />
              ) : null}
            </g>
          ))}
        </svg>

        {/* Priority readout */}
        <AnimatePresence>
          {showMarkers && (
            <motion.div
              initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ delay: reduceMotion ? 0 : 0.9 }}
              className="absolute inset-x-3 bottom-3 rounded-lg border border-white/10 bg-navy/90 p-2 backdrop-blur"
            >
              {MARKERS.map((marker) => (
                <div
                  key={marker.id}
                  className="flex items-center gap-2 px-1 py-0.5 text-[10px] text-white/80"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: DAMAGE_COLORS[marker.code] }}
                  />
                  <span className="font-semibold">{DAMAGE_CLASSES[marker.code].short}</span>
                  <span className="text-white/50">queued for review</span>
                  <span className="ml-auto rounded bg-white/10 px-1 font-mono font-semibold">
                    P{marker.score}
                  </span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
