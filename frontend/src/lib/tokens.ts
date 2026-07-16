/**
 * Chart + status color tokens (hex, consumed by Recharts and MapLibre).
 *
 * The damage-class palette was validated for color-vision-deficiency
 * separation and >=3:1 surface contrast (all-pairs mode, light surface).
 * The one floor-band CVD pair (D10<->D40) is always accompanied by
 * secondary encoding: legends, direct labels, white mark rings, and the
 * table view.
 */
export const DAMAGE_COLORS: Record<string, string> = {
  D00: "#2a78d6", // blue — longitudinal crack
  D10: "#199e70", // teal — transverse crack
  D20: "#c98500", // amber — alligator crack
  D40: "#d03b3b", // vermilion — pothole
};

/** Severity status scale (reserved meaning; always paired with icon + label). */
export const SEVERITY_COLORS: Record<string, string> = {
  low: "#64748b", // slate
  moderate: "#c98500", // amber
  high: "#ec835a", // serious orange
  severe: "#d03b3b", // critical vermilion
};

/** Ordinal one-hue ramp (blue, light -> dark) for ordered buckets. */
export const ORDINAL_BLUE = ["#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab", "#104281"];

/** Series slots for non-class multi-series charts (fixed order, never cycled). */
export const SERIES = {
  blue: "#2a78d6",
  teal: "#199e70",
  amber: "#c98500",
  red: "#d03b3b",
};

export const CHART_INK = {
  axis: "#898781",
  grid: "#e7e5de",
  baseline: "#c9c7bd",
  label: "#52514e",
};

/** Brand hexes for non-Tailwind consumers (map chrome, SVG art). */
export const BRAND_HEX = {
  primary: "#2947ae",
  navy: "#0b1120",
  surface: "#fbfaf7",
};
