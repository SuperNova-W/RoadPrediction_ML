import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleDot,
  Flame,
  MinusCircle,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DAMAGE_COLORS, SEVERITY_COLORS } from "@/lib/tokens";
import {
  DAMAGE_CLASSES,
  type DamageClassCode,
  type ReviewStatus,
  type Severity,
  type WorkOrderStatus,
} from "@/lib/types";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Damage type chip: color swatch + plain-language label (identity, never color-only). */
export function ClassBadge({
  code,
  short = false,
  className,
}: {
  code: DamageClassCode;
  short?: boolean;
  className?: string;
}) {
  return (
    <Badge variant="outline" className={cn("gap-1.5 font-medium", className)}>
      <span
        className="h-2 w-2 rounded-full ring-2 ring-card"
        style={{ backgroundColor: DAMAGE_COLORS[code] }}
        aria-hidden
      />
      {short ? DAMAGE_CLASSES[code].short : DAMAGE_CLASSES[code].label}
    </Badge>
  );
}

const SEVERITY_ICONS: Record<Severity, React.ElementType> = {
  low: MinusCircle,
  moderate: CircleDot,
  high: AlertTriangle,
  severe: Flame,
};

/** Severity chip — status colors are always paired with icon + label. */
export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  const Icon = SEVERITY_ICONS[severity];
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 border-transparent", className)}
      style={{
        color: SEVERITY_COLORS[severity],
        backgroundColor: `${SEVERITY_COLORS[severity]}14`,
      }}
    >
      <Icon aria-hidden />
      {titleCase(severity)}
    </Badge>
  );
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  if (status === "confirmed")
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 aria-hidden /> Confirmed
      </Badge>
    );
  if (status === "rejected")
    return (
      <Badge variant="muted" className="gap-1">
        <XCircle aria-hidden /> Rejected
      </Badge>
    );
  return (
    <Badge variant="warning" className="gap-1">
      <CircleDashed aria-hidden /> Needs review
    </Badge>
  );
}

const WO_VARIANTS: Record<WorkOrderStatus, "muted" | "secondary" | "warning" | "default" | "success"> = {
  planned: "muted",
  approved: "secondary",
  scheduled: "warning",
  in_progress: "default",
  completed: "success",
};

export function WorkOrderBadge({ status }: { status: WorkOrderStatus }) {
  return <Badge variant={WO_VARIANTS[status]}>{titleCase(status)}</Badge>;
}

/** Repair-priority score pill. Numeric value always shown (not color-alone). */
export function PriorityScore({
  score,
  className,
}: {
  score: number;
  className?: string;
}) {
  const tone =
    score >= 80
      ? "bg-destructive/10 text-destructive"
      : score >= 60
        ? "bg-warning/10 text-warning"
        : score >= 40
          ? "bg-primary/10 text-primary"
          : "bg-muted text-muted-foreground";
  return (
    <span
      className={cn(
        "tnum inline-flex min-w-9 items-center justify-center rounded-md px-1.5 py-0.5 text-sm font-semibold",
        tone,
        className,
      )}
    >
      {score}
    </span>
  );
}

/** Letter-grade chip for road-segment condition (A/B teal, C amber, D/F red). */
export function GradeChip({ grade }: { grade: string }) {
  const tone =
    grade === "A" || grade === "B"
      ? "bg-success/10 text-success"
      : grade === "C"
        ? "bg-warning/10 text-warning"
        : "bg-destructive/10 text-destructive";
  return (
    <span
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded-md text-sm font-bold",
        tone,
      )}
    >
      {grade}
    </span>
  );
}
