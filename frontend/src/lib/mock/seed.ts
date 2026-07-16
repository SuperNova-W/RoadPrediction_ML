/** Deterministic PRNG so mock data is stable across renders and reloads. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pick<T>(rand: () => number, arr: readonly T[]): T {
  return arr[Math.floor(rand() * arr.length)];
}

/** Fixed "now" for the demo dataset so timestamps stay coherent. */
export const MOCK_NOW = new Date("2026-07-15T14:00:00-04:00").getTime();

export function hoursAgo(h: number): string {
  return new Date(MOCK_NOW - h * 3600_000).toISOString();
}

export function daysAgo(d: number): string {
  return new Date(MOCK_NOW - d * 86400_000).toISOString();
}

export function daysAhead(d: number): string {
  return new Date(MOCK_NOW + d * 86400_000).toISOString();
}
