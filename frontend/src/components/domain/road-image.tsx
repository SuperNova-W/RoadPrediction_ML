import { mulberry32 } from "@/lib/mock/seed";
import type { DamageClassCode } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Procedurally generated placeholder for a road-facing camera frame.
 * Deterministic per seed so the same issue always renders the same image.
 * Used instead of hotlinked photos; clearly a stylized illustration.
 */
export function RoadImage({
  seed,
  classCode,
  className,
  label = "Illustrative placeholder for a captured road image",
}: {
  seed: number;
  classCode: DamageClassCode;
  className?: string;
  label?: string;
}) {
  const rand = mulberry32(seed);

  // Asphalt speckle
  const speckles = Array.from({ length: 90 }, (_, i) => ({
    key: i,
    cx: rand() * 800,
    cy: 300 + rand() * 200,
    r: 0.6 + rand() * 1.6,
    o: 0.05 + rand() * 0.16,
  }));

  const crackPath = (
    x0: number,
    y0: number,
    x1: number,
    y1: number,
    wobble: number,
    segs = 8,
  ) => {
    let d = `M ${x0} ${y0}`;
    for (let i = 1; i <= segs; i++) {
      const t = i / segs;
      const x = x0 + (x1 - x0) * t + (rand() - 0.5) * wobble;
      const y = y0 + (y1 - y0) * t + (rand() - 0.5) * wobble;
      d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    return d;
  };

  let damage: React.ReactNode = null;
  if (classCode === "D00") {
    const x = 330 + rand() * 140;
    damage = (
      <>
        <path d={crackPath(x, 250, x + (rand() - 0.5) * 60, 500, 26, 12)} stroke="#1c1f26" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.85" />
        <path d={crackPath(x + 8, 300, x + 30, 470, 18, 8)} stroke="#1c1f26" strokeWidth="2" fill="none" opacity="0.6" />
      </>
    );
  } else if (classCode === "D10") {
    const y = 360 + rand() * 90;
    damage = (
      <>
        <path d={crackPath(140, y, 660, y + (rand() - 0.5) * 40, 22, 12)} stroke="#1c1f26" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.85" />
        <path d={crackPath(220, y + 8, 540, y + 20, 14, 8)} stroke="#1c1f26" strokeWidth="2" fill="none" opacity="0.55" />
      </>
    );
  } else if (classCode === "D20") {
    const cx = 300 + rand() * 200;
    const cy = 380 + rand() * 60;
    const web = Array.from({ length: 9 }, (_, i) => {
      const a = (i / 9) * Math.PI * 2 + rand();
      return crackPath(cx, cy, cx + Math.cos(a) * (60 + rand() * 70), cy + Math.sin(a) * (40 + rand() * 50), 18, 5);
    });
    damage = (
      <>
        {web.map((d, i) => (
          <path key={i} d={d} stroke="#1c1f26" strokeWidth={i % 3 === 0 ? 3 : 1.8} fill="none" opacity="0.75" />
        ))}
        <path d={crackPath(cx - 80, cy - 30, cx + 90, cy + 40, 30, 7)} stroke="#1c1f26" strokeWidth="2.4" fill="none" opacity="0.6" />
      </>
    );
  } else {
    const cx = 340 + rand() * 160;
    const cy = 400 + rand() * 60;
    const rx = 55 + rand() * 30;
    const ry = 30 + rand() * 16;
    damage = (
      <>
        <ellipse cx={cx} cy={cy} rx={rx + 10} ry={ry + 7} fill="#23262d" opacity="0.5" />
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="#15171c" />
        <ellipse cx={cx - rx * 0.25} cy={cy - ry * 0.3} rx={rx * 0.55} ry={ry * 0.45} fill="#0d0f13" />
        <path d={crackPath(cx - rx - 30, cy - 10, cx - rx, cy, 12, 4)} stroke="#1c1f26" strokeWidth="2.5" fill="none" opacity="0.7" />
        <path d={crackPath(cx + rx, cy + 5, cx + rx + 40, cy + 18, 12, 4)} stroke="#1c1f26" strokeWidth="2.5" fill="none" opacity="0.7" />
      </>
    );
  }

  return (
    <svg
      viewBox="0 0 800 500"
      role="img"
      aria-label={label}
      className={cn("h-full w-full", className)}
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <linearGradient id={`sky-${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c7d4e2" />
          <stop offset="100%" stopColor="#e6ebf0" />
        </linearGradient>
        <linearGradient id={`road-${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6a7079" />
          <stop offset="100%" stopColor="#40454d" />
        </linearGradient>
      </defs>

      {/* Sky + horizon */}
      <rect width="800" height="240" fill={`url(#sky-${seed})`} />
      <rect y="200" width="800" height="46" fill="#8fa08d" opacity="0.7" />
      <rect y="222" width="800" height="24" fill="#7c8f7a" opacity="0.5" />

      {/* Road: perspective trapezoid */}
      <polygon points="310,240 490,240 800,500 0,500" fill={`url(#road-${seed})`} />
      {/* Shoulder lines */}
      <polygon points="318,240 330,240 60,500 10,500" fill="#d9dade" opacity="0.8" />
      <polygon points="470,240 482,240 790,500 740,500" fill="#d9dade" opacity="0.8" />
      {/* Center dashes */}
      {[0, 1, 2, 3, 4].map((i) => {
        const t0 = i / 5 + 0.02;
        const t1 = i / 5 + 0.1;
        const y0 = 240 + t0 * 260;
        const y1 = 240 + t1 * 260;
        const w0 = 3 + t0 * 14;
        const w1 = 3 + t1 * 14;
        return (
          <polygon
            key={i}
            points={`${400 - w0 / 2},${y0} ${400 + w0 / 2},${y0} ${400 + w1 / 2},${y1} ${400 - w1 / 2},${y1}`}
            fill="#e8d98a"
            opacity="0.9"
          />
        );
      })}

      {/* Asphalt texture */}
      {speckles.map((s) => (
        <circle key={s.key} cx={s.cx} cy={s.cy} r={s.r} fill="#20242b" opacity={s.o} />
      ))}

      {damage}
    </svg>
  );
}
