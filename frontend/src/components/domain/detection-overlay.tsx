"use client";

import { motion, useReducedMotion } from "framer-motion";
import { DAMAGE_COLORS } from "@/lib/tokens";
import { DAMAGE_CLASSES, type Detection } from "@/lib/types";
import { formatConfidence } from "@/lib/format";

/**
 * Animated bounding-box overlay. Renders on top of a relatively-positioned
 * image container; boxes use normalized [0..1] coordinates.
 */
export function DetectionOverlay({
  detections,
  visible = true,
  showLabels = true,
}: {
  detections: Detection[];
  visible?: boolean;
  showLabels?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  if (!visible) return null;

  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      {detections.map((det, i) => {
        const color = DAMAGE_COLORS[det.classCode];
        return (
          <motion.div
            key={det.id}
            className="absolute"
            style={{
              left: `${det.box.x * 100}%`,
              top: `${det.box.y * 100}%`,
              width: `${det.box.width * 100}%`,
              height: `${det.box.height * 100}%`,
            }}
            initial={
              reduceMotion
                ? { opacity: 1 }
                : { opacity: 0, scale: 1.15 }
            }
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              delay: reduceMotion ? 0 : 0.25 + i * 0.18,
              duration: 0.35,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            <div
              className="absolute inset-0 rounded-sm"
              style={{
                border: `2px solid ${color}`,
                boxShadow: `0 0 0 1px rgb(255 255 255 / 0.35), inset 0 0 0 1px rgb(255 255 255 / 0.2)`,
                backgroundColor: `${color}14`,
              }}
            />
            {/* Corner ticks */}
            {[
              "left-0 top-0 border-l-2 border-t-2",
              "right-0 top-0 border-r-2 border-t-2",
              "left-0 bottom-0 border-l-2 border-b-2",
              "right-0 bottom-0 border-r-2 border-b-2",
            ].map((pos) => (
              <span
                key={pos}
                className={`absolute h-2.5 w-2.5 ${pos}`}
                style={{ borderColor: color }}
              />
            ))}
            {showLabels ? (
              <span
                className="absolute -top-6 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
                style={{ backgroundColor: color }}
              >
                {DAMAGE_CLASSES[det.classCode].short} · {formatConfidence(det.confidence)}
              </span>
            ) : null}
          </motion.div>
        );
      })}
    </div>
  );
}
